"""Google Gemini provider via API."""
import json
import os
import urllib.request
import urllib.error
from .base import LLMProvider


class GeminiProvider(LLMProvider):
    name = "Google Gemini"
    model_id = ""

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_id = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    def _call(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent?key={self.api_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini no candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0].get("text", "")
