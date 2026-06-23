"""
providers/api.py — Simplified LLM provider.

Connects to LLM via direct HTTP. No Hermes config, no yaml, no CLI fallback.
Config source (priority):
  1. llm.json at project root (base_url, model, api_key, mode)
  2. LLM_API_KEY env var (overrides api_key in llm.json)
  3. Built-in defaults (openmodel.ai, deepseek-v4-flash)

Change model: edit llm.json → change "model" field. That's it.
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


def call_llm(prompt: str, max_retries: int = 3, system: str | None = None) -> str:
    cfg = _load_config()
    api_key = cfg.get("api_key", "")
    base_url = cfg["base_url"].rstrip("/")
    model = cfg["model"]
    mode = cfg.get("mode", "openai")

    if not api_key:
        raise RuntimeError(
            "No API key found. Set LLM_API_KEY env var or add api_key to llm.json."
        )

    if mode == "anthropic_messages":
        url = f"{base_url}/messages"
        body = {"model": model, "max_tokens": 32000,
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
        body = {"model": model, "messages": messages, "max_tokens": 32000}
        headers = {"Authorization": f"Bearer {api_key}",
                   "Content-Type": "application/json"}
        parse_fn = _parse_openai

    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(), headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                return parse_fn(json.loads(resp.read().decode()))
        except (urllib.error.HTTPError, urllib.error.URLError,
                json.JSONDecodeError, KeyError, ConnectionResetError,
                TimeoutError) as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(1.5)

    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}")


def _parse_anthropic(data: dict) -> str:
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return "\n".join(
        b.get("text", b.get("thinking", "")) for b in data.get("content", [])
    )


def _parse_openai(data: dict) -> str:
    return data["choices"][0]["message"]["content"]
