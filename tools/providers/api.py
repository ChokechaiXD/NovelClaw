"""
providers/api.py — Simplified LLM provider [DEPRECATED - THIN WRAPPER]

Canonical implementations live in tools/translator/backends/.
Default backend: OpenRouter (free Gemma models).
Fallback: openmodel.ai (DeepSeek V4 Flash).
"""

from translator.backends.openrouter import OpenRouterBackend
from translator.backends.openmodel import OpenModelBackend

_or_default = OpenRouterBackend(model="google/gemma-4-26b-a4b-it:free")
_or_fallback = OpenModelBackend()


def call_llm(prompt: str, max_retries: int = 3, system: str | None = None,
             model_override: str | None = None) -> str:
    """Call LLM with fallback support. [DEPRECATED - use translator backends directly]

    Primary: OpenRouter (Gemma 4 26B free)
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

    # Primary: OpenRouter
    try:
        return _or_default.translate(prompt, system=system)
    except Exception:
        pass

    # Fallback: openmodel.ai
    return _or_fallback.translate(prompt, system=system)
