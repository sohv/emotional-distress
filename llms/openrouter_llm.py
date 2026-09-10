# OpenRouter provider: OpenAI chat-completions wire format against the OpenRouter gateway.

import logging
import os

from openai import AsyncOpenAI

from .base import LLMFactory
from .openai_llm import OpenAILLM

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# USD per million tokens, from OpenRouter's /models endpoint. Without these,
# OpenAILLM.calculate_cost silently falls back to gpt-4o rates ($2.50/$10.00)
# for every slug it does not recognise, which is wrong for all of them — it
# overstated haiku-4.5 by 2.3x and understated claude-opus-5 by ~2x.
OPENROUTER_PRICING: dict[str, dict[str, float]] = {
    "openai/gpt-5.2": {"input": 1.75, "output": 14.0},
    "openai/gpt-5.6-sol": {"input": 5.0, "output": 30.0},
    "openai/gpt-4.1-mini": {"input": 0.4, "output": 1.6},
    "anthropic/claude-opus-5": {"input": 5.0, "output": 25.0},
    "anthropic/claude-haiku-4.5": {"input": 1.0, "output": 5.0},
    "moonshotai/kimi-k2.5": {"input": 0.45, "output": 2.25},
    "google/gemini-3.5-flash": {"input": 1.5, "output": 9.0},
    "google/gemini-3.5-flash-20260519": {"input": 1.5, "output": 9.0},
    "anthropic/claude-sonnet-4.5": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4.5": {"input": 5.0, "output": 25.0},
}


# one upstream per family, no fallbacks, so every call in a run is served by the
# same backend. Google AI Studio is what the LiteLLM gemini/ path talks to, which
# puts both routes onto the same servers.
PROVIDER_PINS: dict[str, dict] = {
    "google/": {"order": ["Google AI Studio"], "allow_fallbacks": False},
    "anthropic/": {"order": ["Anthropic"], "allow_fallbacks": False},
}


class OpenRouterLLM(OpenAILLM):
    """OpenAI-compatible client pointed at OpenRouter.

    Model ids keep their full OpenRouter slug (e.g. "anthropic/claude-opus-5"),
    unlike the native openai provider which strips a leading "openai/".
    """

    @property
    def provider_pin(self) -> dict | None:
        return next((pin for prefix, pin in PROVIDER_PINS.items() if self.model.startswith(prefix)), None)

    @property
    def provider(self) -> str:
        return "openrouter"

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Price from the OpenRouter table, or report 0.0 and say so.

        An unpriced model returns 0.0 rather than inheriting the gpt-4o
        fallback: a zero in the totals is visibly missing, while a plausible
        wrong number is not.
        """
        pricing = OPENROUTER_PRICING.get(self.model)
        if pricing is None:
            LOGGER.warning(
                "no OpenRouter price for %s; recording cost_usd=0.0 for this call", self.model
            )
            return 0.0
        return (input_tokens / 1_000_000) * pricing["input"] + (
            output_tokens / 1_000_000
        ) * pricing["output"]

    @classmethod
    def create_client(cls) -> AsyncOpenAI:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        base_url = os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL
        return AsyncOpenAI(api_key=api_key, base_url=base_url)


LLMFactory.register_provider("openrouter", OpenRouterLLM)
