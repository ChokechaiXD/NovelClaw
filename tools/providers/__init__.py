from .base import LLMProvider
from .haiku import HaikuProvider

__all__ = ["LLMProvider", "HaikuProvider", "get_provider"]


def get_provider(name: str | None = None) -> "LLMProvider":
    """Return HaikuProvider (only active provider).

    Kept as a function for future provider expansion; for now there's
    only Haiku, so `name` is ignored.
    """
    return HaikuProvider()
