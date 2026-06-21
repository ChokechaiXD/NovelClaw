"""
providers/api.py — Single Hermes LLM provider.

Connects NovelClaw to the local Hermes Agent's LLM, removing all direct
API-key management from this project. Two modes:

  1. API (preferred)  — POST to Hermes API Server → fast, persistent HTTP
  2. CLI (fallback)   — `hermes chat -Q -q "prompt"` → no server needed

Hermes manages all credentials (OpenRouter, Anthropic, etc.) from its own
.env and config.yaml — no API keys in NovelClaw.
"""

import json
import os
import subprocess
import sys
import time

API_PORT = int(os.environ.get("HERMES_API_PORT", "8877"))
API_URL = f"http://127.0.0.1:{API_PORT}/v1/chat/completions"
MODEL = os.environ.get("HERMES_MODEL", "deepseek-v4-flash")

# ── Helpers ───────────────────────────────────────────────────────────────


def _api_call(prompt: str, max_retries: int = 2) -> str | None:
    """Try Hermes API Server (OpenAI-compatible endpoint)."""
    import urllib.request
    import urllib.error

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8192,
        "temperature": 0.7,
    }).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                API_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
                KeyError, ConnectionResetError, TimeoutError) as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
    return None


def _cli_call(prompt: str, max_retries: int = 2) -> str | None:
    """Fallback: call Hermes via CLI subprocess (no server needed)."""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["hermes", "chat", "-Q", "-q", prompt],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    return None


# ── Public API ────────────────────────────────────────────────────────────

def call_llm(prompt: str, max_retries: int = 3) -> str:
    """Translate a prompt using the local Hermes Agent.

    Tries API Server first (fast), falls back to CLI subprocess.
    All credentials managed by Hermes — no API keys in NovelClaw.
    Handles retry internally.

    Args:
        prompt: The full prompt to send to the LLM
        max_retries: Max retry attempts shared across both modes

    Returns:
        LLM response text

    Raises:
        RuntimeError: if both API and CLI modes fail
    """
    errors = []

    # Try 1: API Server
    result = _api_call(prompt, max_retries=max_retries)
    if result is not None:
        return result
    errors.append("API server unreachable")

    # Try 2: CLI fallback
    result = _cli_call(prompt, max_retries=max_retries)
    if result is not None:
        return result
    errors.append("CLI fallback failed")

    raise RuntimeError(
        f"LLM call failed: {'; '.join(errors)}. "
        f"Ensure Hermes is configured (hermes doctor) or API server is running "
        f"on port {API_PORT} (hermes config set apiserver.enable true + hermes gateway restart)."
    )


def test_connection() -> str:
    """Quick connectivity test — returns 'ok' or error message."""
    result = _api_call("Say 'ok' if you receive this.", max_retries=1)
    if result is not None:
        return f"ok (API mode, {len(result)} chars)"
    result = _cli_call("Say 'ok' if you receive this.", max_retries=1)
    if result is not None:
        return f"ok (CLI mode, {len(result)} chars)"
    return "FAILED: neither API nor CLI mode works"
