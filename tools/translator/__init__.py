"""Translation backends — model providers for LLM calls."""
from .backends.openmodel import OpenModelBackend
from .backends.openrouter import OpenRouterBackend

__all__ = ["OpenModelBackend", "OpenRouterBackend"]
