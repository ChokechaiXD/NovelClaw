"""
tools/llm_router/config_providers.py — YAML-loaded provider config.

Reads tools/config/providers.yaml, resolves environment variables,
and provides a single source of truth for provider configuration.
Used by both the Python translation pipeline and the Express admin UI.

USES PYYAML — must be installed (`pip install pyyaml`).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from atomic_io import atomic_write_json, atomic_write_text

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
        for p in parts[1:]:  # skip "llm", "json" — actual key starts at [2]? No, "llm.json" is one token
            pass
        # Fix: parts are ["llm.json", "openrouter_api_key"]
        # So parts[1:] = ["openrouter_api_key"]
        # But split on "." makes ["llm", "json", "openrouter_api_key"]
        # So parts[2:] = ["openrouter_api_key"] for a 3-element split
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


def _write_llm_json_key(key: str, value: str) -> None:
    llm_path = _PROJECT_ROOT / "llm.json"
    data: dict[str, Any] = {}
    if llm_path.exists():
        try:
            existing = json.loads(llm_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                data = existing
        except (json.JSONDecodeError, OSError):
            data = {}
    data[key] = value
    atomic_write_json(llm_path, data, ensure_ascii=False, indent=2)


def _replace_custom_base_url(text: str, custom_base_url: str) -> str:
    lines = text.splitlines(keepends=True)
    in_custom = False
    custom_indent = None
    updated = False
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if re.match(r"^custom:\s*(?:#.*)?$", stripped):
            in_custom = True
            custom_indent = indent
        elif in_custom and stripped and indent <= (custom_indent or 0):
            in_custom = False
            custom_indent = None

        if in_custom and re.match(r"^base_url:", stripped):
            out.append(re.sub(r'^(\s*base_url:\s*).*', rf'\1"{custom_base_url}"', line))
            updated = True
        else:
            out.append(line)

    return "".join(out) if updated else text


def save_provider_config(active: str | None = None,
                         default_model: str | None = None,
                         discovery_model: str | None = None,
                         custom_base_url: str | None = None,
                         custom_api_key: str | None = None,
                         api_key_provider: str | None = None,
                         api_key: str | None = None) -> bool:
    """Update active provider and/or default model in YAML file.

    Args:
        active: New active provider name (or None to keep).
        default_model: New default model ID (or None to keep).
        discovery_model: New discovery/judge model ID (or None to keep).
        custom_base_url: OpenAI-compatible endpoint for the custom provider.
        custom_api_key: Optional API key for the custom provider, saved to llm.json.
        api_key_provider: Provider name for api_key, saved to llm.json.
        api_key: Optional API key for any provider, saved to llm.json.

    Returns:
        True if saved successfully.
    """
    if not _CONFIG_PATH.exists():
        return False

    text = _CONFIG_PATH.read_text(encoding="utf-8")
    new_lines = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if active is not None and re.match(r"^active:", stripped):
            new_lines.append(re.sub(r"^(\s*active:\s*).*", rf"\1{active}", line))
        elif default_model is not None and re.match(r"^default_model:", stripped):
            # Keep or remove quotes
            new_lines.append(re.sub(r'^(\s*default_model:\s*).*',
                                     rf'\1"{default_model}"', line))
        elif discovery_model is not None and re.match(r"^discovery_model:", stripped):
            new_lines.append(re.sub(r'^(\s*discovery_model:\s*).*',
                                     rf'\1"{discovery_model}"', line))
        else:
            new_lines.append(line)

    text = "".join(new_lines)
    if custom_base_url is not None:
        text = _replace_custom_base_url(text, custom_base_url.strip())
    atomic_write_text(_CONFIG_PATH, text)
    if custom_api_key is not None and custom_api_key.strip():
        _write_llm_json_key("custom_api_key", custom_api_key.strip())
    if api_key_provider is not None and api_key is not None and api_key.strip():
        key = _provider_key_field(api_key_provider.strip())
        _write_llm_json_key(key, api_key.strip())
        if api_key_provider.strip() == "openmodel":
            _write_llm_json_key("api_key", api_key.strip())
    clear_provider_config_cache()
    return True


def get_active_provider_and_model() -> tuple[str, str]:
    """Get (active_provider, default_model)."""
    cfg = get_provider_config()
    return cfg.get("active", "openmodel"), cfg.get("default_model", "deepseek-v4-flash")


def get_discovery_model() -> str:
    """Get discovery/judge model (separate from translate model)."""
    cfg = get_provider_config()
    return cfg.get("discovery_model", cfg.get("default_model", "deepseek-v4-flash"))


def _model_label(model_id: str) -> str:
    return model_id.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ").strip() or model_id


def _model_catalog(models: list[Any], source: str = "static") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for model in models:
        if isinstance(model, str):
            model_id = model
            item = {"id": model_id, "name": _model_label(model_id), "tier": source}
        elif isinstance(model, dict):
            model_id = str(model.get("id") or "").strip()
            if not model_id:
                continue
            item = {
                "id": model_id,
                "name": model.get("name") or _model_label(model_id),
                "tier": model.get("tier") or source,
            }
        else:
            continue
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        result.append(item)
    return result


def discover_provider_models(provider_name: str, timeout_sec: float = 8.0) -> dict[str, Any]:
    """Fetch the current model list from a provider's /models endpoint.

    Returns a small status dict and never raises for expected network/provider
    failures. Static config stays the fallback for offline/local-first use.
    """
    cfg = get_provider_config()
    providers = cfg.get("providers", {})
    pcfg = providers.get(provider_name, {}) if isinstance(providers, dict) else {}
    if not isinstance(pcfg, dict):
        return {"ok": False, "models": [], "error": f"Unknown provider: {provider_name}"}

    base_url = str(pcfg.get("base_url") or "").rstrip("/")
    if not base_url:
        return {"ok": False, "models": [], "error": "Provider has no base_url"}

    headers = {"Accept": "application/json"}
    api_key = str(pcfg.get("api_key") or "").strip()
    if provider_name == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(f"{base_url}/models", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "models": [], "error": str(exc)[:200]}

    raw_models = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_models, list):
        return {"ok": False, "models": [], "error": "Provider returned an unsupported model list"}

    models = _model_catalog(raw_models, "live")
    return {"ok": True, "models": models, "error": ""}


def get_providers_list(refresh: bool = False) -> list[dict[str, Any]]:
    """Get list of available providers with their models, for Admin UI."""
    cfg = get_provider_config()
    providers = cfg.get("providers", {})
    if not isinstance(providers, dict):
        return []
    result = []
    for name, pcfg in providers.items():
        if isinstance(pcfg, dict):
            static_models = _model_catalog(pcfg.get("models", []), "static")
            models = static_models
            model_source = "static"
            model_error = ""
            if refresh:
                discovered = discover_provider_models(name)
                if discovered.get("ok") and discovered.get("models"):
                    models = discovered["models"]
                    model_source = "live"
                else:
                    model_error = discovered.get("error", "")
            result.append({
                "name": name,
                "display_name": pcfg.get("display_name", name),
                "base_url": pcfg.get("base_url", ""),
                "has_key": bool(pcfg.get("api_key")),
                "key_field": _provider_key_field(name),
                "models": models,
                "model_source": model_source,
                "model_error": model_error,
            })
    return result


if __name__ == "__main__":
    cfg = get_provider_config()
    print(json.dumps({
        "active": cfg.get("active"),
        "default_model": cfg.get("default_model"),
        "providers": list(cfg.get("providers", {}).keys()),
    }, indent=2, ensure_ascii=False))
    plist = get_providers_list()
    for p in plist:
        models = p.get("models", [])
        print(f"  {p['name']} ({p['display_name']}): {len(models)} models")
        for m in models[:2]:
            print(f"    - {m.get('id', '?')} ({m.get('tier', '?')})")
