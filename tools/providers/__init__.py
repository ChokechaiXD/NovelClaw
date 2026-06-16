from .base import LLMProvider
from .haiku import HaikuProvider
from .gemini import GeminiProvider
from .claude import ClaudeProvider

__all__ = ["LLMProvider", "HaikuProvider", "GeminiProvider", "ClaudeProvider"]


def get_provider(name: str | None = None) -> "LLMProvider":
    """Factory: returns LLMProvider by name (reads LLM_PROVIDER env if None)."""
    import os
    if name is None:
        name = os.environ.get("LLM_PROVIDER", "haiku").lower()

    providers = {
        "haiku": HaikuProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
    }
    cls = providers.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider: {name}. Choose from: {list(providers.keys())}")
    return cls()


__all__ = ["LLMProvider", "HaikuProvider", "GeminiProvider", "ClaudeProvider", "get_provider"]
