"""Claude Haiku provider via subprocess (existing workflow)."""
import subprocess
from .base import LLMProvider


class HaikuProvider(LLMProvider):
    name = "Claude Haiku"
    model_id = "claude-sonnet-haiku-20241022"

    def _call(self, prompt: str) -> str:
        """Call Claude Haiku via subprocess (existing Hermes workflow)."""
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

