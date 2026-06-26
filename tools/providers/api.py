import json
import os
from pathlib import Path

from translator.backends.openrouter import OpenRouterBackend
from translator.backends.openmodel import OpenModelBackend

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LLM_CONFIG_PATH = _PROJECT_ROOT / "llm.json"
_or_fallback = OpenModelBackend()


def _get_default_backend():
    model = "google/gemma-4-26b-a4b-it:free"
    provider = "openrouter"
    
    if _LLM_CONFIG_PATH.exists():
        try:
            cfg = json.loads(_LLM_CONFIG_PATH.read_text(encoding="utf-8"))
            if cfg.get("default_model"):
                model = cfg["default_model"]
            if cfg.get("default_provider"):
                provider = cfg["default_provider"]
        except Exception:
            pass
            
    if provider == "openmodel":
        return OpenModelBackend(model_override=model)
    return OpenRouterBackend(model=model)


def call_llm(prompt: str, max_retries: int = 3, system: str | None = None,
             model_override: str | None = None) -> str:
    """Call LLM with fallback support. [DEPRECATED - use translator backends directly]

    Primary: OpenRouter or custom model from llm.json
    Fallback: openmodel.ai (DeepSeek V4 Flash)

    Args:
        prompt: User text.
        max_retries: Ignored in wrapper (handled by caller).
        system: System prompt (optional).
        model_override: Specific model override.

    Returns:
        Response text.
    """
    if model_override:
        bk = OpenRouterBackend(model=model_override)
        try:
            return bk.translate(prompt, system=system)
        except Exception:
            pass
        bk2 = OpenModelBackend(model_override=model_override)
        return bk2.translate(prompt, system=system)

    # Primary: Dynamic backend from llm.json
    try:
        bk = _get_default_backend()
        return bk.translate(prompt, system=system)
    except Exception:
        pass

    # Fallback: openmodel.ai
    return _or_fallback.translate(prompt, system=system)
