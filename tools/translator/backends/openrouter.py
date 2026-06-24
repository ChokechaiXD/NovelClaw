"""OpenRouter backend — OpenRouter API (Gemma, GPT-OSS, free models).

Uses OpenAI-compatible format. Supports model fallback chaining
via OpenRouter's built-in provider routing.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .base import TranslatorBackend

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LLM_CONFIG_PATH = _PROJECT_ROOT / "llm.json"


class OpenRouterBackend(TranslatorBackend):
    """Backend for OpenRouter — free tier models with fallback."""

    def __init__(self, model: str = "openrouter/owl-alpha"):
        self._model = model
        self._base_url = "https://openrouter.ai/api/v1"

        # Load API key
        self._api_key = ""
        if _LLM_CONFIG_PATH.exists():
            try:
                cfg = json.loads(_LLM_CONFIG_PATH.read_text(encoding="utf-8"))
                self._api_key = os.environ.get("OPENROUTER_API_KEY") or cfg.get("api_key", "")
            except Exception:
                pass
        # Also check direct env var
        env_key = os.environ.get("OPENROUTER_API_KEY")
        if env_key:
            self._api_key = env_key

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "openrouter"

    def translate(self, prompt: str, system: str | None = None,
                  **kwargs) -> str:
        if not self._api_key:
            raise RuntimeError("OpenRouter: No API key configured")

        timeout = kwargs.get("timeout_sec", 90)
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.3)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "provider": {
                "allow_fallbacks": True,
                "sort": {"by": "throughput", "partition": "none"},
            },
        }

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content or ""
