"""Claude Haiku provider via subprocess (existing workflow)."""
import subprocess
import os
from .base import LLMProvider


class HaikuProvider(LLMProvider):
    name = "Claude Haiku"
    model_id = "claude-sonnet-haiku-20241022"

    def _call(self, prompt: str) -> str:
        """Call Claude Haiku via subprocess (existing Hermes integration)."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return self._call_direct(prompt, api_key)
        return self._call_subprocess(prompt)

    def _call_direct(self, prompt: str, api_key: str) -> str:
        """Direct Anthropic API call (placeholder, falls back to subprocess)."""
        return self._call_subprocess(prompt)

    def _call_subprocess(self, prompt: str) -> str:
        """Call via subprocess (existing Hermes workflow)."""
        result = subprocess.run(
            ["hermes", "prompt"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(f"Hermes failed (rc={result.returncode}): {result.stderr}")
        return result.stdout
