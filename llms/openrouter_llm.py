# OpenRouter provider: OpenAI chat-completions wire format against the OpenRouter gateway.

import os

from openai import AsyncOpenAI

from .base import LLMFactory
from .openai_llm import OpenAILLM

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLM(OpenAILLM):
    """OpenAI-compatible client pointed at OpenRouter.

    Model ids keep their full OpenRouter slug (e.g. "anthropic/claude-opus-5"),
    unlike the native openai provider which strips a leading "openai/".
    """

    @property
    def provider(self) -> str:
        return "openrouter"

    @classmethod
    def create_client(cls) -> AsyncOpenAI:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        base_url = os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL
        return AsyncOpenAI(api_key=api_key, base_url=base_url)


LLMFactory.register_provider("openrouter", OpenRouterLLM)
