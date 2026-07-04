"""LLM provider adapter for the translation pipeline."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from llm_rate_limit import limit_llm_call


def get_active_config(provider_name: str | None = None) -> dict[str, Any]:
    """Get active provider + model from config_providers."""
    from llm_router.config_providers import get_provider_config

    cfg = get_provider_config()
    active = provider_name or cfg.get("active", "openrouter")
    providers = cfg.get("providers", {})
    pcfg = providers.get(active, {})
    base_url = pcfg.get("base_url", "https://openrouter.ai/api/v1")
    api_key = pcfg.get("api_key", "")
    default_model = cfg.get("default_model", "google/gemma-4-26b-a4b-it:free")
    discovery_model = cfg.get("discovery_model", default_model)
    timeout = pcfg.get("timeout_sec", 90)
    max_tokens = pcfg.get("max_tokens", 4096)
    temperature = pcfg.get("temperature", 0.28)

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": default_model,
        "discovery_model": discovery_model,
        "timeout": timeout,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "provider_name": active,
    }


def call_llm(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    timeout: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[str, str, str]:
    """Direct HTTP call to the active LLM provider.

    Returns:
        (response_text, provider_name, model_name)
    """
    cfg = get_active_config(provider)
    if model:
        cfg["model"] = model
    if timeout is not None:
        cfg["timeout"] = timeout
    if max_tokens is not None:
        cfg["max_tokens"] = max_tokens
    if temperature is not None:
        cfg["temperature"] = temperature

    base_url = cfg["base_url"].rstrip("/")
    api_key = cfg["api_key"]
    model_name = cfg["model"]
    timeout_sec = cfg.get("timeout", 90)
    max_tok = cfg.get("max_tokens", 4096)
    temp = cfg.get("temperature", 0.28)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    url = f"{base_url}/chat/completions"
    body = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tok,
        "temperature": temp,
    }

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )

    try:
        with limit_llm_call(cfg["provider_name"]):
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode())
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content, cfg["provider_name"], model_name
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500] if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}") from e
