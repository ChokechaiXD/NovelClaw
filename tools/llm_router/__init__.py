"""
tools/llm_router — Provider-agnostic LLM fallback router.

Z.AI free model whitelist (HARD GUARD):
  - glm-4.7-flash       ✅ Free
  - glm-4.5-flash       ✅ Free
  - glm-4.6v-flash      ✅ Free (vision)
  - Anything else        ❌ REJECTED (paid) unless ALLOW_PAID_MODELS=true

Profiles:
  translate → Z.AI glm-4.7-flash → OpenRouter owl-alpha → openrouter/free
  validate  → OpenRouter nemotron-3-ultra → gpt-oss-120b → Z.AI glm-4.7-flash
  polish    → Z.AI glm-4.7-flash → Gemma 4 31B → openrouter/free
  code      → OpenRouter poolside/laguna → north-mini-code → owl-alpha
  fast      → Z.AI glm-4.5-flash → glm-4.7-flash → openrouter/free
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
