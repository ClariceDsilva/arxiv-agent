from __future__ import annotations

import os

from .base import LLMClient

DEFAULT_MODEL = "gemini-3.1-flash-lite"
# Free tier (Google AI Studio, checked Sept 2026): 15 requests/min,
# 500 requests/day, 250K tokens/min. See README "Rate limits" section.


class GeminiClient(LLMClient):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey"
            )
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json" if json_mode else "text/plain",
            temperature=0.2,
        )
        response = self._client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=config,
        )
        return response.text or ""
