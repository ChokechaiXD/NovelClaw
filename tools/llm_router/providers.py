"""
tools/llm_router/providers.py — Low-level HTTP callers [CONSOLIDATED]

Canonical implementations now live in tools/translator/backends/.
This module re-exports via PROVIDER_DISPATCH for backward compat.

Supported providers: openmodel, openrouter, z_ai
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from translator.backends.openmodel import OpenModelBackend
from translator.backends.openrouter import OpenRouterBackend


def _log(msg: str) -> None:
    print(f"  [router] {msg}", file=sys.stderr, flush=True)


# ── Z.AI (deprecated — kept for backward compat) ──────────────────────

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

    extra_body = {"thinking": {"type": "disabled"}}

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


# ── Providers using new backends ──────────────────────────────────────

def call_openmodel(
    prompt: str,
    system: str | None = None,
    model: str = "deepseek-v4-flash",
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.35,
) -> str:
    """Call openmodel.ai via consolidated backend."""
    backend = OpenModelBackend(model_override=model)
    return backend.translate(prompt, system=system,
                             timeout_sec=timeout_sec,
                             max_tokens=max_tokens,
                             temperature=temperature)


def call_openrouter(
    prompt: str,
    system: str | None = None,
    model: str = "openrouter/owl-alpha",
    timeout_sec: int = 90,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Call OpenRouter via consolidated backend."""
    backend = OpenRouterBackend(model=model)
    return backend.translate(prompt, system=system,
                             timeout_sec=timeout_sec,
                             max_tokens=max_tokens,
                             temperature=temperature)


# ── Shared helper ─────────────────────────────────────────────────────

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
    return content or ""


# ── Dispatch map ──────────────────────────────────────────────────────

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
    for entry in PROFILES.get("translate", []):
        if entry.get("provider") == provider:
            return entry["model"]
    return "unknown"
