"""providers — Direct HTTP LLM providers.

All LLM calls go through direct HTTP to configured providers.
No Hermes Agent dependency. API keys via llm.json or env vars.
"""

from .api import call_llm

__all__ = ["call_llm"]
