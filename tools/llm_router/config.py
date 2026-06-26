"""
LLM Router Config — profile chains, provider config, guards.
"""

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Provider config ─────────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

def _load_keys() -> dict:
    keys = {"openrouter": ""}
    keys["openrouter"] = os.environ.get("OPENROUTER_API_KEY", "")
    if keys["openrouter"]:
        return keys
    llm_path = _PROJECT_ROOT / "llm.json"
    if llm_path.exists():
        try:
            import json
            with open(llm_path, encoding="utf-8") as f:
                cfg = json.load(f)
            if not keys["openrouter"]:
                keys["openrouter"] = cfg.get("openrouter_api_key", "")
        except (json.JSONDecodeError, OSError):
            pass
    return keys

_KEYS = _load_keys()
OPENROUTER_API_KEY = _KEYS["openrouter"]

# ── Profile chains (June 2026 — verified free models on OpenRouter) ─────
PROFILES: dict[str, list[dict]] = {
    "translate_fast": [
        {
            "provider": "openrouter",
            "model": "google/gemma-4-26b-a4b-it:free",
            "timeout_sec": 80,
            "max_tokens": 4096,
            "temperature": 0.28,
        },
        {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
            "timeout_sec": 100,
            "max_tokens": 4096,
            "temperature": 0.28,
        },
        {
            "provider": "openrouter",
            "model": "openai/gpt-oss-120b:free",
            "timeout_sec": 90,
            "max_tokens": 4096,
            "temperature": 0.2,
        },
        {
            "provider": "openrouter",
            "model": "openrouter/free",
            "timeout_sec": 75,
            "max_tokens": 2048,
            "temperature": 0.25,
        },
    ],
    "translate_quality": [
        {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
            "timeout_sec": 110,
            "max_tokens": 8192,
            "temperature": 0.25,
        },
        {
            "provider": "openrouter",
            "model": "google/gemma-4-26b-a4b-it:free",
            "timeout_sec": 85,
            "max_tokens": 4096,
            "temperature": 0.26,
        },
        {
            "provider": "openrouter",
            "model": "openai/gpt-oss-120b:free",
            "timeout_sec": 90,
            "max_tokens": 4096,
            "temperature": 0.15,
        },
        {
            "provider": "openrouter",
            "model": "openrouter/free",
            "timeout_sec": 75,
            "max_tokens": 2048,
            "temperature": 0.25,
        },
    ],
    "validate": [
        {
            "provider": "openrouter",
            "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "timeout_sec": 120,
            "max_tokens": 4096,
            "temperature": 0.05,
        },
        {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
            "timeout_sec": 100,
            "max_tokens": 2048,
            "temperature": 0.05,
        },
        {
            "provider": "openrouter",
            "model": "openrouter/free",
            "timeout_sec": 75,
            "max_tokens": 1536,
            "temperature": 0.05,
        },
    ],
    "polish": [
        {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
            "timeout_sec": 100,
            "max_tokens": 4096,
            "temperature": 0.35,
        },
        {
            "provider": "openrouter",
            "model": "google/gemma-4-26b-a4b-it:free",
            "timeout_sec": 80,
            "max_tokens": 4096,
            "temperature": 0.35,
        },
        {
            "provider": "openrouter",
            "model": "openrouter/free",
            "timeout_sec": 75,
            "max_tokens": 2048,
            "temperature": 0.3,
        },
    ],
    "fast": [
        {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
            "timeout_sec": 45,
            "max_tokens": 2048,
            "temperature": 0.2,
        },
        {
            "provider": "openrouter",
            "model": "openrouter/free",
            "timeout_sec": 45,
            "max_tokens": 1024,
            "temperature": 0.2,
        },
    ],
}


def _get_dynamic_default() -> dict | None:
    llm_path = _PROJECT_ROOT / "llm.json"
    if llm_path.exists():
        try:
            import json
            with open(llm_path, encoding="utf-8") as f:
                cfg = json.load(f)
            model = cfg.get("default_model")
            provider = cfg.get("default_provider", "openrouter")
            if model:
                return {"provider": provider, "model": model}
        except Exception:
            pass
    return None


def get_profile(name: str) -> list[dict]:
    if name not in PROFILES:
        raise KeyError(f"Unknown profile '{name}'. Available: {list(PROFILES.keys())}")
    
    chain = list(PROFILES[name])
    
    if name in ("translate_fast", "translate_quality"):
        dynamic = _get_dynamic_default()
        if dynamic:
            chain = [item for item in chain if not (item["provider"] == dynamic["provider"] and item["model"] == dynamic["model"])]
            new_item = {
                "provider": dynamic["provider"],
                "model": dynamic["model"],
                "timeout_sec": 95,
                "max_tokens": 4096,
                "temperature": 0.28 if name == "translate_fast" else 0.25
            }
            chain.insert(0, new_item)
            
    return chain


def list_profiles() -> list[str]:
    return list(PROFILES.keys())
