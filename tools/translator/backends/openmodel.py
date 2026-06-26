"""OpenModel backend — openmodel.ai (DeepSeek V4 Flash, free).

Uses anthropic_messages format. Loads config from llm.json or defaults.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .base import TranslatorBackend

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LLM_CONFIG_PATH = _PROJECT_ROOT / "llm.json"

_DEFAULTS = {
    "base_url": "https://api.openmodel.ai/v1",
    "model": "deepseek-v4-flash",
    "mode": "anthropic_messages",
}


class OpenModelBackend(TranslatorBackend):
    """Backend for openmodel.ai — primary free translation model."""

    def __init__(self, model_override: str | None = None):
        cfg = dict(_DEFAULTS)
        if _LLM_CONFIG_PATH.exists():
            try:
                with open(_LLM_CONFIG_PATH) as f:
                    cfg.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        env_key = os.environ.get("LLM_API_KEY")
        if env_key:
            cfg["api_key"] = env_key
        elif cfg.get("openmodel_api_key"):
            cfg["api_key"] = cfg["openmodel_api_key"]

        self._model = model_override or cfg.get("model", "deepseek-v4-flash")
        self._base_url = cfg["base_url"].rstrip("/")
        self._api_key = cfg.get("api_key", "")
        self._mode = cfg.get("mode", "openai")

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "openmodel"

    def translate(self, prompt: str, system: str | None = None,
                  **kwargs) -> str:
        if not self._api_key:
            raise RuntimeError("OpenModel: No API key configured")

        timeout = kwargs.get("timeout_sec", 600)
        max_tokens = kwargs.get("max_tokens", 32000)
        temperature = kwargs.get("temperature", 0.35)

        if self._mode == "anthropic_messages":
            url = f"{self._base_url}/messages"
            body = {
                "model": self._model,
                "max_tokens": max_tokens,
                "thinking": {"type": "disabled"},
            }
            if system:
                body["system"] = system
            body["messages"] = [{"role": "user", "content": prompt}]
            headers = {"x-api-key": self._api_key, "Content-Type": "application/json"}
            parse_fn = self._parse_anthropic
        else:
            url = f"{self._base_url}/chat/completions"
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            body = {
                "model": self._model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            headers = {"Authorization": f"Bearer {self._api_key}",
                       "Content-Type": "application/json"}
            parse_fn = self._parse_openai

        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_fn(json.loads(resp.read().decode()))

    @staticmethod
    def _parse_anthropic(data: dict) -> str:
        for block in data.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        return "\n".join(
            b.get("text", b.get("thinking", "")) for b in data.get("content", [])
        )

    @staticmethod
    def _parse_openai(data: dict) -> str:
        return data["choices"][0]["message"]["content"]
