"""Base class for all translator backends.

All backends must implement translate() and expose model/provider properties.
"""

from abc import ABC, abstractmethod


class TranslatorBackend(ABC):
    """Abstract interface for translation LLM backends.

    All backends (openmodel, openrouter, dedicated MT) implement this.
    """

    @property
    @abstractmethod
    def model(self) -> str:
        """Model name (e.g. 'deepseek-v4-flash', 'google/gemma-4-31b-it:free')."""
        ...

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider name (e.g. 'openmodel', 'openrouter')."""
        ...

    @abstractmethod
    def translate(self, prompt: str, system: str | None = None,
                  **kwargs) -> str:
        """Send a prompt to the model and return the response text.

        Args:
            prompt: User message text
            system: System prompt (optional)
            **kwargs: Backend-specific overrides (temperature, max_tokens, etc.)

        Returns:
            Response text as string.

        Raises:
            RuntimeError: If the LLM call fails after retries.
        """
        ...
