"""Gemini through the LiteLLM Python SDK, talking to Google directly.

Why this exists: routing Gemini over OpenRouter's OpenAI-compatible chat
completions endpoint does not work in this harness. `gemini-3-flash-preview`
completed 2.9% of rollouts (2/68) — the model makes two useful tool calls, then
repeats `list_files` until it hits the iteration cap, with empty assistant text
throughout. `gemini-3.5-flash` behaved the same way at $1.24/rollout, ~30x
gpt-5.2. It is a tool-result formatting problem, not a refusal.

The existing `litellm` provider does not help: it is an OpenAI client pointed at
a LiteLLM *proxy server* (LITELLM_API_KEY / LITELLM_BASE_URL), which this
project does not run. This provider uses the LiteLLM *SDK* instead, so
LiteLLM's own Gemini message translation does the work and no proxy is needed.
It authenticates with GOOGLE_API_KEY against Google AI Studio.

Model ids keep LiteLLM's provider prefix, e.g. `gemini/gemini-3.5-flash`.
"""

import os
from collections.abc import Sequence

from utils.functions_runtime import (
    EmptyEnv,
    Function,
    FunctionsRuntime,
    TaskEnvironment,
)
from utils.pipeline_elements import QueryResult
from utils.types import ChatMessage

import litellm

from .base import LLMFactory
from .litellm_llm import (
    LiteLLM,
    _function_to_openai,
    _message_to_openai,
    _openai_to_assistant_message,
)

# LiteLLM otherwise emits a provider-list banner on first use.
litellm.suppress_debug_info = True


class GeminiLiteLLM(LiteLLM):
    """Gemini via the LiteLLM SDK, using GOOGLE_API_KEY against Google directly.

    Inherits message conversion, token counting and the `_MODEL_PRICING`
    scaffolding from LiteLLM; overrides the request path, which is the only part
    that assumed a proxy.
    """

    def __init__(
        self,
        client: None = None,
        model: str = "gemini/gemini-3.5-flash",
        temperature: float | None = 1.0,
        max_tokens: int | None = 8192,
    ) -> None:
        super().__init__(client=None, model=model, temperature=temperature, max_tokens=max_tokens)
        self.api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY (or GEMINI_API_KEY) is required for the gemini_litellm provider")

    @property
    def provider(self) -> str:
        return "gemini_litellm"

    @classmethod
    def create_client(cls) -> None:
        """No client object: the LiteLLM SDK is called at module level."""
        return None

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Price from LiteLLM's model table rather than a hardcoded map.

        Falls back to 0.0 for models LiteLLM does not know yet, so a missing
        price entry never aborts a run. Cost then under-reports rather than
        crashing, which run.log makes visible.
        """
        try:
            in_cost, out_cost = litellm.cost_per_token(
                model=self.model,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
            return in_cost + out_cost
        except Exception:
            return 0.0

    async def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: TaskEnvironment = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict | None = None,
    ) -> QueryResult:
        if extra_args is None:
            extra_args = {}

        openai_tools = [_function_to_openai(tool) for tool in runtime.functions.values()]
        openai_messages = [_message_to_openai(message) for message in messages]

        completion = await litellm.acompletion(
            model=self.model,
            messages=openai_messages,
            tools=openai_tools or None,
            tool_choice="auto" if openai_tools else None,
            temperature=extra_args.get("temperature", self.temperature),
            max_tokens=self.max_tokens,
            api_key=self.api_key,
            # Gemini rejects several OpenAI-only fields; let LiteLLM drop them
            # rather than failing the call.
            drop_params=True,
            num_retries=5,
        )

        if completion.choices:
            output = _openai_to_assistant_message(completion.choices[0].message)
        else:
            output = _openai_to_assistant_message(
                type("M", (), {"content": "", "tool_calls": None})()
            )

        usage = completion.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = self.calculate_cost(input_tokens, output_tokens)

        extra_args.setdefault("usage", []).append(
            {
                "model": self.model,
                "provider": "gemini_litellm",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": getattr(usage, "total_tokens", input_tokens + output_tokens),
                "cost_usd": cost,
            }
        )

        return QueryResult(
            query=query,
            runtime=runtime,
            env=env,
            messages=[*messages, output],
            extra_args=extra_args,
        )

    async def count_tokens(
        self,
        messages: Sequence[ChatMessage] = None,
        system_prompt: str = None,
        text: str = None,
        tools: list[Function] = None,
    ) -> int:
        """Approximate with the inherited tiktoken counter.

        Gemini's tokenizer differs, so this is an estimate. It is only used for
        context-budget bookkeeping, never for billing — billing comes from the
        usage block the API returns.
        """
        return await super().count_tokens(
            messages=messages, system_prompt=system_prompt, text=text, tools=tools
        )


LLMFactory.register_provider("gemini_litellm", GeminiLiteLLM)
