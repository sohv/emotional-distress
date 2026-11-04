# Tinker provider: OpenAI chat-completions wire format against Tinker's OpenAI-compatible endpoint, for LoRA checkpoints.

import logging
import os
from pathlib import Path

import yaml
from openai import AsyncOpenAI

from .base import LLMFactory
from .openai_llm import OpenAILLM

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
# stable aliases ("tinker/<name>") mapped to the tinker:// sampler path each checkpoint was saved to
CHECKPOINTS = Path(__file__).resolve().parents[1] / "configs" / "tinker_checkpoints.yaml"


def resolve(alias: str) -> str:
    paths = yaml.safe_load(CHECKPOINTS.read_text())
    if alias not in paths:
        raise ValueError(f"{alias} is not in {CHECKPOINTS}")
    return paths[alias]


class _Completions:
    """Stands in for client.chat.completions and sends the checkpoint path in place of the alias."""

    def __init__(self, inner, path: str, sequential_tools: bool) -> None:
        self._inner, self._path, self._sequential = inner, path, sequential_tools

    async def create(self, **kwargs):
        # gpt-oss otherwise issues every tool call in one turn and writes its report before reading the data
        extra = {"parallel_tool_calls": False} if self._sequential and kwargs.get("tools") else {}
        return await self._inner.create(**{**kwargs, **extra, "model": self._path})


class _Client:
    def __init__(self, client: AsyncOpenAI, path: str, sequential_tools: bool) -> None:
        self.chat = type("Chat", (), {"completions": _Completions(client.chat.completions, path, sequential_tools)})()


class TinkerLLM(OpenAILLM):
    """Calls a Tinker sampler checkpoint; the alias stays the model name the harness and transcripts see."""

    def __init__(self, client: AsyncOpenAI, model: str, temperature: float | None = 0.0, max_tokens: int | None = 8192) -> None:
        super().__init__(_Client(client, resolve(model), "gpt-oss" in model), model, temperature, max_tokens)

    @property
    def provider(self) -> str:
        return "tinker"

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # tinker bills sampling on its own account, not per call through this harness
        return 0.0

    @classmethod
    def create_client(cls) -> AsyncOpenAI:
        api_key = os.environ.get("TINKER_API_KEY")
        if not api_key:
            raise ValueError("TINKER_API_KEY environment variable is required")
        return AsyncOpenAI(api_key=api_key, base_url=os.environ.get("TINKER_OAI_BASE_URL") or DEFAULT_BASE_URL)


LLMFactory.register_provider("tinker", TinkerLLM)
