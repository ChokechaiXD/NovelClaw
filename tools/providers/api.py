"""
providers/api.py — Single NovelClaw LLM provider.

Connects NovelClaw to the configured LLM via direct HTTP calls.
Reads credentials from the local Hermes Agent config — zero API keys
in NovelClaw source code or .env.

Mode order (fastest first):
  1. Direct HTTP → configured model API (~5s per call)
  2. Hermes CLI fallback (slower, subprocess overhead)
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
    """Load API credentials from Hermes config.yaml (read-only, no copy made)."""
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

    # Fallback: minimal defaults
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
    cfg = _load_hermes_config()
    return cfg.get("model", {})


def _get_api_key() -> str:
    return _get_model_config().get("api_key", "")


def _get_base_url() -> str:
    return _get_model_config().get("base_url", "https://api.openmodel.ai/v1")


def _get_model() -> str:
    return _get_model_config().get("default", "deepseek-v4-flash")


def _get_api_mode() -> str:
    return _get_model_config().get("api_mode", "openai")


# ── Direct HTTP call ──────────────────────────────────────────────────


def _direct_call(prompt: str, max_retries: int = 2) -> str | None:
    """Call the model API directly via HTTP (Anthropic Messages or OpenAI format).

    Reads credentials from Hermes config. ~5s per call when working.
    """
    import urllib.request
    import urllib.error

    api_key = _get_api_key()
    base_url = _get_base_url().rstrip("/")
    model = _get_model()
    api_mode = _get_api_mode()

    if not api_key:
        return None

    if api_mode == "anthropic_messages":
        # Anthropic Messages API format (used by openmodel.ai proxy)
        url = f"{base_url}/messages"
        body = json.dumps({
            "model": model,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        _parse = _parse_anthropic_response
    else:
        # OpenAI-compatible format (OpenRouter, standard)
        url = f"{base_url}/chat/completions"
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,
        }).encode()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        _parse = _parse_openai_response

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
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

    Response format:
    {"content": [{"type": "thinking", ...}, {"type": "text", "text": "..."}], ...}
    """
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    # Fallback: return all content blocks joined
    parts = [b.get("text", b.get("thinking", "")) for b in data.get("content", [])]
    return "\n".join(parts)


def _parse_openai_response(data: dict) -> str:
    """Extract text from OpenAI-compatible API response."""
    return data["choices"][0]["message"]["content"]


# ── CLI fallback ──────────────────────────────────────────────────────


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
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    return None


# ── Public API ────────────────────────────────────────────────────────


def call_llm(prompt: str, max_retries: int = 3) -> str:
    """Translate a prompt using the configured LLM.

    Priority: direct HTTP → CLI fallback.
    All credentials managed by Hermes config.yaml — zero API keys in NovelClaw.

    Args:
        prompt: The full prompt to send to the LLM
        max_retries: Max retry attempts shared across all modes

    Returns:
        LLM response text

    Raises:
        RuntimeError: if all modes fail
    """
    errors = []

    # Try 1: Direct HTTP (fastest, ~5s)
    result = _direct_call(prompt, max_retries=max_retries)
    if result is not None:
        return result
    errors.append("direct HTTP call failed")

    # Try 2: CLI fallback
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
