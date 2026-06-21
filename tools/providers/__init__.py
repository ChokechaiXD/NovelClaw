"""providers — Single Hermes LLM provider.

All LLM calls go through the local Hermes Agent.
No API keys managed in NovelClaw.
"""

from .api import call_llm, test_connection

__all__ = ["call_llm", "test_connection"]
