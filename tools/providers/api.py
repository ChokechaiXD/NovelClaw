"""
providers/api.py — Simplified LLM provider [DEPRECATED - THIN WRAPPER]

Canonical implementations live in tools/translator/backends/.
This file re-exports for backward compatibility.
"""

from translator.backends.openmodel import OpenModelBackend

_backend = OpenModelBackend()


def call_llm(prompt: str, max_retries: int = 3, system: str | None = None,
             model_override: str | None = None) -> str:
    """Call LLM with fallback support. [DEPRECATED - use translator backends directly]

    Args:
        prompt: User text.
        max_retries: Ignored in wrapper (handled by caller).
        system: System prompt (optional).
        model_override: Specific model override.

    Returns:
        Response text.
    """
    if model_override:
        bk = OpenModelBackend(model_override=model_override)
        return bk.translate(prompt, system=system)
    return _backend.translate(prompt, system=system)
