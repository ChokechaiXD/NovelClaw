"""LLM provider adapter for the translation pipeline."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from llm_rate_limit import limit_llm_call


@lru_cache(maxsize=1)
def _load_central_config() -> dict[str, Any]:
    """Load novelclaw.config.yaml from project root."""
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "novelclaw.config.yaml")
    if not os.path.exists(path):
        return {}
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_active_config(provider_name: str | None = None) -> dict[str, Any]:
    """Get active provider + model, reading novelclaw.config.yaml first."""
    from llm_router.config_providers import get_provider_config

    central = _load_central_config()
    yaml_cfg = get_provider_config()

    active = provider_name or central.get("provider") or yaml_cfg.get("active") or "openrouter"
    providers = yaml_cfg.get("providers", {})
    pcfg = providers.get(active, {})

    default_model = central.get("model") or yaml_cfg.get("default_model") or "google/gemma-4-26b-a4b-it:free"
    discovery_model = central.get("discovery_model") or yaml_cfg.get("discovery_model") or default_model

    temperature = central.get("temperature") or pcfg.get("temperature") or 0.28
    max_tokens = central.get("max_tokens") or pcfg.get("max_tokens") or 4096
    timeout = central.get("timeout_sec") or pcfg.get("timeout_sec") or 90

    base_url = pcfg.get("base_url", "https://openrouter.ai/api/v1")
    api_key = pcfg.get("api_key", "")

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


# _do_request was removed — call_llm handles HTTP inline with full retry logic.


def call_llm(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    timeout: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[str, str, str]:
    """Direct HTTP call to the active LLM provider with retries.

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
    timeout_sec = cfg.get("timeout", 240)
    max_tok = cfg.get("max_tokens", 4096)
    temp = cfg.get("temperature", 0.28)

    # ── Model validation: only allowed model prefixes ──
    ALLOWED_PREFIXES = {"openrouter/", "poli/", "9router/", "custom/"}
    if not any(model_name.startswith(p) for p in ALLOWED_PREFIXES):
        raise ValueError(
            f"Model '{model_name}' blocked. Translation pipeline may only use "
            f"models starting with: {', '.join(sorted(ALLOWED_PREFIXES))}. "
            f"Set NOVELCLAW_ALLOWED_MODEL_PREFIXES env var to override."
        )

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

    max_attempts = 3
    last_error = ""

    for attempt in range(max_attempts):
        try:
            with limit_llm_call(cfg["provider_name"]):
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    raw = resp.read().decode().strip()
                if raw.endswith("data: [DONE]"):
                    raw = raw[: -len("data: [DONE]")].strip()
                json_start = raw.find("{")
                if json_start >= 0:
                    raw = raw[json_start:]
                data = json.loads(raw)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content and len(content.strip()) >= 5:
                return content, cfg["provider_name"], model_name
            # Empty/short content — retry
            last_error = f"empty_or_short_content ({len(content.strip()) if content else 0} chars)"
            time.sleep(1)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_error = f"parse_error: {e}"
            time.sleep(1.5)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()[:500] if e.fp else ""
            last_error = f"HTTP {e.code}: {err_body[:100]}"
            if e.code == 429:
                time.sleep(5)
            elif e.code >= 500:
                time.sleep(3)
            else:
                time.sleep(1.5)
        except urllib.error.URLError as e:
            last_error = f"connection: {e.reason}"
            time.sleep(2)

    raise RuntimeError(
        f"LLM call failed after {max_attempts} attempts: {last_error}"
    )
