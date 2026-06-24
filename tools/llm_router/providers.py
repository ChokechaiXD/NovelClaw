"""
LLM Router Providers — low-level HTTP callers for Z.AI and OpenRouter.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Log helper — writes to stderr so stdout stays clean for JSON-mode
def _log(msg: str) -> None:
    print(f"  [router] {msg}", file=sys.stderr, flush=True)


def _call_openai_compat(
    base_url: str,
    model: str,
    messages: list[dict],
    api_key: str,
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    extra_body: dict | None = None,
) -> str:
    """Call an OpenAI-compatible chat completions endpoint."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra_body:
        body.update(extra_body)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read().decode())

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if content is None:
        content = ""
    return content


def call_zai(
    prompt: str,
    system: str | None = None,
    model: str = "glm-4.7-flash",
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.35,
) -> str:
    """Call Z.AI API. OpenAI-compatible endpoint."""
    from .config import ZAI_BASE_URL, ZAI_API_KEY, check_zai_model

    check_zai_model(model)

    if not ZAI_API_KEY:
        raise RuntimeError("ZAI_API_KEY not set in environment")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    extra_body = {
        "thinking": {"type": "disabled"},
    }

    return _call_openai_compat(
        base_url=ZAI_BASE_URL,
        model=model,
        messages=messages,
        api_key=ZAI_API_KEY,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=extra_body,
    )


def call_openrouter(
    prompt: str,
    system: str | None = None,
    model: str = "openrouter/owl-alpha",
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Call OpenRouter API. Supports model= for fallback chaining."""
    from .config import OPENROUTER_BASE_URL, OPENROUTER_API_KEY

    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    extra_body = {
        "provider": {
            "allow_fallbacks": True,
            "sort": {"by": "throughput", "partition": "none"},
        }
    }

    return _call_openai_compat(
        base_url=OPENROUTER_BASE_URL,
        model=model,
        messages=messages,
        api_key=OPENROUTER_API_KEY,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=extra_body,
    )


# ── Dispatch map ─────────────────────────────────────────────────────────

def call_openmodel(
    prompt: str,
    system: str | None = None,
    model: str = "deepseek-v4-flash",
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.35,
) -> str:
    """Call openmodel.ai (DeepSeek V4 Flash) — always available, free, working key."""
    from .config import OPENMODEL_BASE_URL, OPENMODEL_API_KEY

    if not OPENMODEL_API_KEY:
        raise RuntimeError("OPENMODEL_API_KEY not set — check llm.json api_key")

    # Uses anthropic_messages format
    url = f"{OPENMODEL_BASE_URL.rstrip('/')}/messages"
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    if system:
        body["system"] = system
    body["messages"] = [{"role": "user", "content": prompt}]
    headers = {"x-api-key": OPENMODEL_API_KEY, "Content-Type": "application/json"}

    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read().decode())

    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return ""


PROVIDER_DISPATCH = {
    "openmodel": call_openmodel,
    "z_ai": call_zai,
    "openrouter": call_openrouter,
}


def call_provider(
    provider_name: str,
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Dispatch to the correct provider function."""
    fn = PROVIDER_DISPATCH.get(provider_name)
    if fn is None:
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {list(PROVIDER_DISPATCH.keys())}")
    if model is None:
        model = _default_model(provider_name)
    return fn(
        prompt=prompt,
        system=system,
        model=model,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _default_model(provider: str) -> str:
    from .config import PROFILES
    # Default: use first translate profile entry
    for entry in PROFILES.get("translate", []):
        if entry.get("provider") == provider:
            return entry["model"]
    return "unknown"
