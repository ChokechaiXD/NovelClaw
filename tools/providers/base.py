"""Abstract base class for LLM providers."""
from abc import ABC, abstractmethod
import os


class LLMProvider(ABC):
    """Base class for all LLM providers (Haiku, Gemini, Claude).

    Subclasses must implement:
        - name: human-readable provider name (e.g. "Claude Haiku")
        - model_id: model identifier for the API
        - _call(prompt: str) -> str: the actual API call
    """

    name: str = "base"
    model_id: str = ""

    @abstractmethod
    def _call(self, prompt: str) -> str:
        """Execute the LLM API call. Implement in subclass."""
        ...

    def translate(self, prompt: str, max_retries: int = 3) -> str:
        """Call LLM with retry logic.

        Args:
            prompt: The full prompt to send
            max_retries: Max retry attempts on failure

        Returns:
            LLM response text

        Raises:
            RuntimeError: if all retries fail
        """
        import time
        last_error = None
        for attempt in range(max_retries):
            try:
                return self._call(prompt)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff
        raise RuntimeError(f"{self.name} failed after {max_retries} retries: {last_error}") from last_error
