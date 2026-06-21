from .base import LLMProvider
from .haiku import HaikuProvider

__all__ = ["LLMProvider", "HaikuProvider", "get_provider"]


def get_provider() -> "LLMProvider":
    """Return HaikuProvider (the only active provider).

    Callers should not pass a model name; routing will be added when
    there is more than one provider.
    """
    return HaikuProvider()
