from __future__ import annotations

import os

from .base import EchoLLMClient, LLMClient


def get_llm_client(provider: str | None = None) -> LLMClient:
    """provider: 'gemini' | 'ollama' | 'echo'. Defaults to $LLM_PROVIDER,
    then falls back to 'gemini' if GEMINI_API_KEY is set, else 'ollama'.
    """
    provider = provider or os.environ.get("LLM_PROVIDER")
    if not provider:
        provider = "gemini" if os.environ.get("GEMINI_API_KEY") else "ollama"

    if provider == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient()
    if provider == "ollama":
        from .ollama_client import OllamaClient
        return OllamaClient()
    if provider == "echo":
        return EchoLLMClient()
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected gemini/ollama/echo)")
