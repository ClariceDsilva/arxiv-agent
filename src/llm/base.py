from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Minimal interface every provider backend implements.

    Kept deliberately narrow (one method) so swapping providers - or
    injecting a fake for tests - never requires touching node code.
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """Return the model's text response. If json_mode is True, the
        implementation should coax the provider into returning raw JSON
        (no markdown fences) where possible; callers still defensively
        strip fences before parsing.
        """
        raise NotImplementedError


class EchoLLMClient(LLMClient):
    """Trivial fake used in tests / offline dry-runs. Not for real use."""

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        return "[EchoLLMClient] no real model configured; set GEMINI_API_KEY or run Ollama."
