"""
tools/llm_router — Provider-agnostic LLM fallback router.

Profiles defined in config.py (translate_fast, translate_quality, validate, polish, fast).
Each profile has a fallback chain with circuit breaker and output validation.
"""

from .router import RouterConfig, call_profile, call_with_fallback
from .health import HealthTracker
from .validators import validate_translate_response, validate_chapter_json

__all__ = [
    "RouterConfig",
    "call_profile",
    "call_with_fallback",
    "HealthTracker",
    "validate_translate_output",
]
