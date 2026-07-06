"""
tools/llm_router/config_providers.py — YAML-loaded provider config.

Reads tools/config/providers.yaml, resolves environment variables,
and provides a single source of truth for provider configuration.
Used by the translation pipeline (pipeline_llm.py → call_llm).

Core only. CLI / Admin UI functions live in config_admin.py.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "providers.yaml"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_refs(obj: Any, config_refs: dict[str, Any] | None = None) -> Any:
    """Recursively resolve env var refs (${VAR}) and file-based keys."""
    if isinstance(obj, str):
        # Resolve ${VAR}
        def _env_replace(m: re.Match) -> str:
            name = m.group(1)
            if config_refs and name in config_refs:
                return str(config_refs.get(name) or "")
            return os.environ.get(name, "")
        obj = re.sub(r"\$\{(\w+)\}", _env_replace, obj)

        # Resolve llm.json.key.xxx
        if obj.startswith("llm.json.key."):
            key_path = obj.split(".")[2:]  # e.g. ['openrouter_api_key']
            llm_path = _PROJECT_ROOT / "llm.json"
            if llm_path.exists():
                try:
                    data: Any = json.loads(llm_path.read_text(encoding="utf-8"))
                    for k in key_path:
                        if isinstance(data, dict):
                            data = data.get(k, "")
                        else:
                            data = ""
                            break
                    return data if data else ""
                except (json.JSONDecodeError, OSError):
                    return ""
            return ""
        return obj

    if isinstance(obj, dict):
        return {k: _resolve_refs(v, config_refs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v, config_refs) for v in obj]
    return obj


def _resolve_file_key(value: str) -> str:
    """Resolve 'llm.json.xxx.yyy' references by reading llm.json."""
    if not value or not value.startswith("llm.json."):
        return ""
    parts = value.split(".")
    # parts = ["llm", "json", "key1", "key2", ...]
    llm_path = _PROJECT_ROOT / "llm.json"
    if not llm_path.exists():
        return ""
    try:
        data: Any = json.loads(llm_path.read_text(encoding="utf-8"))
        if len(parts) >= 3:
            key_path = parts[2:]
        else:
            key_path = parts[1:]
        for k in key_path:
            if isinstance(data, dict):
                data = data.get(k, "")
            else:
                data = ""
                break
        return str(data) if data else ""
    except (json.JSONDecodeError, OSError):
        return ""


def _provider_key_field(provider_name: str) -> str:
    if provider_name == "openmodel":
        return "openmodel_api_key"
    return f"{provider_name}_api_key"


def _resolve_local_provider_key(provider_name: str) -> str:
    key = _resolve_file_key(f"llm.json.{_provider_key_field(provider_name)}")
    return key or (_resolve_file_key("llm.json.api_key") if provider_name == "openmodel" else "")


@lru_cache(maxsize=1)
def _load_provider_config() -> dict[str, Any]:
    """Load and resolve provider config from providers.yaml."""
    if not _CONFIG_PATH.exists():
        return {"active": "openmodel", "default_model": "deepseek-v4-flash",
                "providers": {}, "profiles": []}

    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    config_refs = {
        "active": raw.get("active", ""),
        "default_model": raw.get("default_model", ""),
        "discovery_model": raw.get("discovery_model", raw.get("default_model", "")),
    }
    resolved = _resolve_refs(raw, config_refs)

    # Resolve file-based API keys (api_key_file → api_key)
    providers = resolved.get("providers", {})
    if isinstance(providers, dict):
        for name, pcfg in providers.items():
            if isinstance(pcfg, dict):
                file_key = pcfg.get("api_key_file", "")
                if file_key and not pcfg.get("api_key", ""):
                    rk = _resolve_file_key(file_key)
                    if rk:
                        pcfg["api_key"] = rk
                if not pcfg.get("api_key", ""):
                    lk = _resolve_local_provider_key(name)
                    if lk:
                        pcfg["api_key"] = lk

    return resolved


def clear_provider_config_cache() -> None:
    """Clear cached provider config after writes or test path changes."""
    _load_provider_config.cache_clear()


def get_provider_config() -> dict[str, Any]:
    """Return resolved provider config from providers.yaml.

    Returns resolved config dict with:
    - active: str
    - default_model: str
    - providers: dict
    - profiles: list
    """
    return deepcopy(_load_provider_config())
