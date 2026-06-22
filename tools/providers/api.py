"""
providers/api.py — Single NovelClaw LLM provider.

Connects NovelClaw to the configured LLM via direct HTTP calls.
Reads credentials from the local Hermes Agent config — zero API keys
in NovelClaw source code or .env.

Mode order (fastest first):
  1. Direct HTTP → configured model API (~5s per call)
  2. Hermes CLI fallback (slower, subprocess overhead)

Research-informed fixes (2026-06-22):
- DeepSeek V4 Flash defaults to thinking mode when using Anthropic Messages API.
  Thinking consumes output tokens from the same max_tokens budget, leaving
  ~2000 tokens for actual translation — not enough for full chapters.
  Fix: explicit thinking: {"type": "disabled"} and max_tokens=32000.
- Use `system` field (Anthropic format) for language constraints, not
  inline in user message — gives better control.
- Source: api-docs.deepseek.com/guides/thinking_mode + community testing.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


# ── Read credentials from Hermes config ────────────────────────────────

_HERMES_CONFIG = None

def _load_hermes_config() -> dict:
    global _HERMES_CONFIG
    if _HERMES_CONFIG is not None:
        return _HERMES_CONFIG

    config_paths = [
        Path(os.environ.get("HERMES_CONFIG", "")),
        Path.home() / ".hermes" / "config.yaml",
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "config.yaml",
        Path(os.environ.get("APPDATA", "")) / "hermes" / "config.yaml",
    ]

    for p in config_paths:
        if p.exists():
            try:
                import yaml
                _HERMES_CONFIG = yaml.safe_load(p.read_text(encoding="utf-8"))
                return _HERMES_CONFIG
            except Exception:
                continue

    _HERMES_CONFIG = {
        "model": {
            "base_url": "https://api.openmodel.ai/v1",
            "default": "deepseek-v4-flash",
            "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            "api_mode": "anthropic_messages",
        }
    }
    return _HERMES_CONFIG


def _get_model_config() -> dict:
    return _load_hermes_config().get("model", {})


def _get_api_key() -> str:
    return _get_model_config().get("api_key", "")


def _get_base_url() -> str:
    return _get_model_config().get("base_url", "https://api.openmodel.ai/v1")


def _get_model() -> str:
    return _get_model_config().get("default", "deepseek-v4-flash")


def _get_api_mode() -> str:
    return _get_model_config().get("api_mode", "openai")


# ── Direct HTTP call ──────────────────────────────────────────────────


def _direct_call(prompt: str, max_retries: int = 2, system: str | None = None) -> str | None:
    """Call the model API directly via HTTP.

    Args:
        prompt: User message content
        max_retries: Retry attempts
        system: Optional system prompt (used as Anthropic `system` field,
                or prepended to user message for OpenAI format)

    Research notes (2026-06-22):
    - DeepSeek V4 Flash uses thinking mode by default with Anthropic API.
      This eats output tokens — up to 6K tokens just for thinking.
      Explicit `thinking: {"type": "disabled"}` forces non-thinking mode,
      giving the full max_tokens budget to translation output.
    - max_tokens=32000 for full chapter translation (~3K-8K output tokens).
    """
    import urllib.request
    import urllib.error

    api_key = _get_api_key()
    base_url = _get_base_url().rstrip("/")
    model = _get_model()
    api_mode = _get_api_mode()

    if not api_key:
        return None

    REQUEST_TIMEOUT = 600  # chapters can take 1-5 minutes

    if api_mode == "anthropic_messages":
        url = f"{base_url}/messages"
        body_parts = {
            "model": model,
            "max_tokens": 32000,
            "thinking": {"type": "disabled"},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body_parts["system"] = system
        body = json.dumps(body_parts).encode()
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }
        _parse = _parse_anthropic_response
    else:
        url = f"{base_url}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": 32000,
        }).encode()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        _parse = _parse_openai_response

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return _parse(data)
        except (urllib.error.HTTPError, urllib.error.URLError,
                json.JSONDecodeError, KeyError, ConnectionResetError,
                TimeoutError) as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
    return None


def _parse_anthropic_response(data: dict) -> str:
    """Extract text from Anthropic Messages API response.

    DeepSeek V4 with thinking disabled returns content as text blocks.
    Response: {"content": [{"type": "text", "text": "..."}], ...}
    """
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    parts = [b.get("text", b.get("thinking", "")) for b in data.get("content", [])]
    return "\n".join(parts)


def _parse_openai_response(data: dict) -> str:
    return data["choices"][0]["message"]["content"]


def _cli_call(prompt: str, max_retries: int = 2) -> str | None:
    """Fallback: call Hermes via CLI subprocess."""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["hermes", "chat", "-Q", "-q", prompt],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    return None


# ── Public API ────────────────────────────────────────────────────────


def call_llm(prompt: str, max_retries: int = 3, system: str | None = None) -> str:
    """Translate a prompt using the configured LLM.

    Priority: direct HTTP → CLI fallback.
    All credentials managed by Hermes config.yaml — zero API keys in NovelClaw.

    Args:
        prompt: The full prompt to send to the LLM
        max_retries: Max retry attempts shared across all modes
        system: Optional system prompt (used for language constraints)

    Returns:
        LLM response text

    Raises:
        RuntimeError: if all modes fail
    """
    errors = []

    result = _direct_call(prompt, max_retries=max_retries, system=system)
    if result is not None:
        return result
    errors.append("direct HTTP call failed")

    result = _cli_call(prompt, max_retries=max_retries)
    if result is not None:
        return result
    errors.append("CLI fallback failed")

    raise RuntimeError(
        f"LLM call failed: {'; '.join(errors)}. "
        f"Check Hermes config or API key."
    )


def test_connection() -> str:
    """Quick connectivity test — returns 'ok' or error message."""
    result = _direct_call("Say 'ok' if you receive this.", max_retries=1)
    if result is not None:
        return f"ok (direct HTTP, {len(result)} chars)"
    result = _cli_call("Say 'ok' if you receive this.", max_retries=1)
    if result is not None:
        return f"ok (CLI mode, {len(result)} chars)"
    return "FAILED: neither HTTP nor CLI mode works"
