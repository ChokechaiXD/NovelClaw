"""
providers/api.py — Simplified LLM provider with fallback model support.

Connects to LLM via direct HTTP. Supports fallback models when primary fails.

Config source (priority):
  1. llm.json at project root (base_url, model, api_key, mode, fallbacks)
  2. LLM_API_KEY env var (overrides api_key in llm.json)
  3. Built-in defaults (openmodel.ai, deepseek-v4-flash)

Fallback config in llm.json:
  {
    "base_url": "https://api.openmodel.ai/v1",
    "model": "deepseek-v4-flash",
    "api_key": "...",
    "mode": "anthropic_messages",
    "fallbacks": [
      {"name": "gemma-4-31b", "base_url": "https://api.openmodel.ai/v1",
       "model": "gemma-4-31b-it", "mode": "openai"}
    ]
  }

call_llm() auto-tries fallbacks in order when primary call fails.
translate_one() in translate.py uses fallback on quality gate failure.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LLM_CONFIG_PATH = _PROJECT_ROOT / "llm.json"

_DEFAULTS = {
    "base_url": "https://api.openmodel.ai/v1",
    "model": "deepseek-v4-flash",
    "mode": "openai",
}


def _load_config() -> dict:
    cfg = dict(_DEFAULTS)
    if _LLM_CONFIG_PATH.exists():
        try:
            with open(_LLM_CONFIG_PATH) as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    # Env var takes priority for API key (most sensitive)
    env_key = os.environ.get("LLM_API_KEY")
    if env_key:
        cfg["api_key"] = env_key
    return cfg


def call_llm(prompt: str, max_retries: int = 3, system: str | None = None,
             model_override: str | None = None) -> str:
    """Call LLM with automatic fallback support.

    Args:
        prompt: User text to send.
        max_retries: Max retry attempts per model (default 3).
        system: System prompt (optional).
        model_override: Force a specific model (bypasses primary).
                        Use full model name or 'fallback:N' to use N-th fallback
                        (1-indexed, e.g. 'fallback:1' = first fallback).

    Returns:
        Response text from the LLM.

    Raises:
        RuntimeError: If all models + retries fail.
    """
    cfg = _load_config()

    # Build list of (model_name, base_url, api_key, mode) to try
    candidates = []

    if model_override:
        # model_override can be:
        # "fallback:1" → first fallback
        # "gemma-4-31b-it" → direct model name (use primary base_url)
        if model_override.startswith("fallback:"):
            idx = int(model_override.split(":", 1)[1]) - 1
            fallbacks = cfg.get("fallbacks", [])
            if 0 <= idx < len(fallbacks):
                fb = fallbacks[idx]
                candidates.append((
                    fb.get("model", "unknown"),
                    fb.get("base_url", cfg["base_url"]).rstrip("/"),
                    fb.get("api_key", cfg.get("api_key", "")),
                    fb.get("mode", cfg.get("mode", "openai")),
                ))
            else:
                raise RuntimeError(f"Fallback index {idx + 1} out of range ({len(fallbacks)} available)")
        else:
            # Direct model override — use primary base_url and api_key
            candidates.append((
                model_override,
                cfg["base_url"].rstrip("/"),
                cfg.get("api_key", ""),
                cfg.get("mode", "openai"),
            ))
    else:
        # Primary model first
        candidates.append((
            cfg.get("model", "unknown"),
            cfg["base_url"].rstrip("/"),
            cfg.get("api_key", ""),
            cfg.get("mode", "openai"),
        ))
        # Then fallbacks
        for fb in cfg.get("fallbacks", []):
            candidates.append((
                fb.get("model", "unknown"),
                fb.get("base_url", cfg["base_url"]).rstrip("/"),
                fb.get("api_key", cfg.get("api_key", "")),
                fb.get("mode", cfg.get("mode", "openai")),
            ))

    last_err = None

    for model_name, base_url, api_key, mode in candidates:
        if not api_key:
            last_err = RuntimeError("No API key configured")
            continue

        if mode == "anthropic_messages":
            url = f"{base_url}/messages"
            body = {"model": model_name, "max_tokens": 32000,
                    "thinking": {"type": "disabled"}}
            if system:
                body["system"] = system
            body["messages"] = [{"role": "user", "content": prompt}]
            headers = {"x-api-key": api_key, "Content-Type": "application/json"}
            parse_fn = _parse_anthropic
        else:
            url = f"{base_url}/chat/completions"
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            body = {"model": model_name, "messages": messages, "max_tokens": 32000}
            headers = {"Authorization": f"Bearer {api_key}",
                       "Content-Type": "application/json"}
            parse_fn = _parse_openai

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url, data=json.dumps(body).encode(), headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=600) as resp:
                    text = parse_fn(json.loads(resp.read().decode()))
                    # Log which model succeeded
                    _log_model(model_name)
                    return text
            except (urllib.error.HTTPError, urllib.error.URLError,
                    json.JSONDecodeError, KeyError, ConnectionResetError,
                    TimeoutError) as e:
                last_err = e
                status_hint = ""
                if isinstance(e, urllib.error.HTTPError):
                    status_hint = f" HTTP {e.code}"
                if attempt < max_retries - 1:
                    time.sleep(1.5 + attempt * 0.5)

        # Model exhausted — log and try next
        import sys as _sys
        print(f"  ⚠ Model '{model_name}' failed after {max_retries} retries{status_hint if status_hint else ''}",
              file=_sys.stderr, flush=True)

    raise RuntimeError(
        f"LLM call failed after {len(candidates)} models × {max_retries} retries: {last_err}"
    )


def _log_model(model_name: str) -> None:
    """Log which model was used (to stderr for hermetic tracking)."""
    import sys as _sys
    print(f"  ✓ LLM response from: {model_name}", file=_sys.stderr, flush=True)


def _parse_anthropic(data: dict) -> str:
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return "\n".join(
        b.get("text", b.get("thinking", "")) for b in data.get("content", [])
    )


def _parse_openai(data: dict) -> str:
    return data["choices"][0]["message"]["content"]
