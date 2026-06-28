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
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "providers.yaml"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_refs(obj: Any) -> Any:
    """Recursively resolve env var refs (${VAR}) and file-based keys."""
    if isinstance(obj, str):
        # Resolve ${VAR}
        def _env_replace(m: re.Match) -> str:
            return os.environ.get(m.group(1), "")
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
        return {k: _resolve_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v) for v in obj]
    return obj


def get_provider_config() -> dict[str, Any]:
    """Load and resolve provider config from providers.yaml.

    Returns resolved config dict with:
    - active: str
    - default_model: str
    - providers: dict
    - profiles: list
    """
    if not _CONFIG_PATH.exists():
        return {"active": "openmodel", "default_model": "deepseek-v4-flash",
                "providers": {}, "profiles": []}

    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    resolved = _resolve_refs(raw)

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

    return resolved


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


def save_provider_config(active: str | None = None,
                         default_model: str | None = None) -> bool:
    """Update active provider and/or default model in YAML file.

    Args:
        active: New active provider name (or None to keep).
        default_model: New default model ID (or None to keep).

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
        else:
            new_lines.append(line)

    _CONFIG_PATH.write_text("".join(new_lines), encoding="utf-8")
    return True


def get_active_provider_and_model() -> tuple[str, str]:
    """Get (active_provider, default_model)."""
    cfg = get_provider_config()
    return cfg.get("active", "openmodel"), cfg.get("default_model", "deepseek-v4-flash")


def get_discovery_model() -> str:
    """Get discovery/judge model (separate from translate model)."""
    cfg = get_provider_config()
    return cfg.get("discovery_model", cfg.get("default_model", "deepseek-v4-flash"))


def get_providers_list() -> list[dict[str, Any]]:
    """Get list of available providers with their models, for Admin UI."""
    cfg = get_provider_config()
    providers = cfg.get("providers", {})
    if not isinstance(providers, dict):
        return []
    result = []
    for name, pcfg in providers.items():
        if isinstance(pcfg, dict):
            result.append({
                "name": name,
                "display_name": pcfg.get("display_name", name),
                "models": pcfg.get("models", []),
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
