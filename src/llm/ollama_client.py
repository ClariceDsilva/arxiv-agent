from __future__ import annotations

import os

import requests

from .base import LLMClient

DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_HOST = "http://localhost:11434"


class OllamaClient(LLMClient):
    """Talks to a local Ollama server. No API key, fully offline.

    Setup: `ollama pull qwen2.5:7b-instruct` (or any instruct model you
    have) and make sure `ollama serve` is running.
    """

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.host = host or os.environ.get("OLLAMA_HOST", DEFAULT_HOST)

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=180)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running "
                f"and have you pulled '{self.model}'? ({exc})"
            ) from exc
        return resp.json().get("response", "")
