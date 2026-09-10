import json
import logging
import os
from collections.abc import Sequence

import openai
import tiktoken
from openai import AsyncOpenAI
from openai._types import NOT_GIVEN
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import FunctionDefinition
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_random_exponential
from utils.functions_runtime import (
    EmptyEnv,
    Function,
    FunctionCall,
    FunctionsRuntime,
    TaskEnvironment,
)
from utils.pipeline_elements import QueryResult
from utils.types import ChatAssistantMessage, ChatMessage

from .base import BaseLLM, LLMFactory


LOGGER = logging.getLogger(__name__)

def _tool_call_to_openai(tool_call: FunctionCall) -> ChatCompletionMessageToolCallParam:
    if tool_call.id is None:
        raise ValueError("`tool_call.id` is required for OpenAI")
    return ChatCompletionMessageToolCallParam(
        id=tool_call.id,
        type="function",
        function={
            "name": tool_call.function,
            "arguments": json.dumps(tool_call.args),
        },
    )


def _message_to_openai(message: ChatMessage) -> ChatCompletionMessageParam:
    match message["role"]:
        case "system":
            return ChatCompletionSystemMessageParam(role="system", content=message["content"])
        case "user":
            return ChatCompletionUserMessageParam(role="user", content=message["content"])
        case "assistant":
            if message.get("tool_calls") is not None and len(message.get("tool_calls", [])) > 0:
                tool_calls = [_tool_call_to_openai(tool_call) for tool_call in message["tool_calls"]]
                out = ChatCompletionAssistantMessageParam(
                    role="assistant",
                    content=message["content"],
                    tool_calls=tool_calls,
                )
                # Anthropic requires its signed thinking blocks replayed verbatim,
                # otherwise interleaved thinking silently stops after turn one.
                if message.get("reasoning_details"):
                    out["reasoning_details"] = message["reasoning_details"]
                return out
            out = ChatCompletionAssistantMessageParam(
                role="assistant",
                content=message["content"],
            )
            if message.get("reasoning_details"):
                out["reasoning_details"] = message["reasoning_details"]
            return out
        case "tool":
            if message["tool_call_id"] is None:
                raise ValueError("`tool_call_id` should be specified for OpenAI.")
            return ChatCompletionToolMessageParam(
                content=message["error"] or message["content"],
                tool_call_id=message["tool_call_id"],
                role="tool",
                name=message["tool_call"].function,  # type: ignore -- this is actually used, and is important!
            )
        case _:
            raise ValueError(f"Invalid message type: {message}")


def _openai_to_tool_call(tool_call: ChatCompletionMessageToolCall) -> FunctionCall:
    """Convert an OpenAI tool call to a FunctionCall.

    Args:
        tool_call: The OpenAI tool call to convert

    Returns:
        FunctionCall: The converted function call

    Raises:
        ValueError: If the tool call arguments cannot be parsed as JSON
    """
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        print(f"Failed to parse tool call arguments. Full tool call: {tool_call}")
        print(f"JSON decode error: {str(e)}")
        raise ValueError(f"Invalid JSON in tool call arguments: {str(e)}")

    return FunctionCall(
        function=tool_call.function.name,
        args=args,
        id=tool_call.id,
    )


def _openai_to_assistant_message(message: ChatCompletionMessage) -> ChatAssistantMessage:
    """Convert an OpenAI message to an assistant message.

    Args:
        message: The OpenAI message to convert

    Returns:
        ChatAssistantMessage: The converted assistant message

    Raises:
        ValueError: If any tool calls in the message have invalid JSON arguments
    """

    content = message.content
    # OpenRouter returns the trace as `reasoning`; some providers use
    # `reasoning_content`. Keep it in its own field so it stays separable from
    # the model's visible answer rather than being spliced into content.
    reasoning = (
        getattr(message, "reasoning", None)
        or getattr(message, "reasoning_content", None)
        or None
    )
    if reasoning is None:
        details = getattr(message, "reasoning_details", None)
        if details:
            texts = [
                d.get("text") or d.get("summary")
                for d in details
                if isinstance(d, dict) and (d.get("text") or d.get("summary"))
            ]
            reasoning = "\n".join(t for t in texts if t) or None

    if message.tool_calls is not None:
        tool_calls = []
        for tool_call in message.tool_calls:
            try:
                tool_calls.append(_openai_to_tool_call(tool_call))
            except ValueError:
                print(f"Error processing tool call. Full tool call: {tool_call}")
                continue
    else:
        tool_calls = None
    return ChatAssistantMessage(
        role="assistant", content=content, tool_calls=tool_calls,
        reasoning_content=reasoning,
        reasoning_details=getattr(message, "reasoning_details", None),
    )


def _function_to_openai(f: Function) -> ChatCompletionToolParam:
    function_definition = FunctionDefinition(
        name=f.name,
        description=f.description,
        parameters=f.parameters.model_json_schema(),
    )
    return ChatCompletionToolParam(type="function", function=function_definition)


@retry(
    wait=wait_random_exponential(multiplier=10, max=120),
    stop=stop_after_attempt(10),
    reraise=True,
    retry=retry_if_not_exception_type((openai.BadRequestError, ValueError)),
)
async def chat_completion_request(
    client: AsyncOpenAI,
    model: str,
    messages: Sequence[ChatCompletionMessageParam],
    tools: Sequence[ChatCompletionToolParam],
    temperature: float | None = 0.0,
    return_usage: bool = True,
    max_tokens: int | None = None,
    user: str | None = None,
    thinking: bool | None = None,
    use_json_format: bool = False,
    reasoning_max_tokens: int | None = None,
    provider_pin: dict | None = None,
):
    """Make a chat completion request to OpenAI with retries.

    Args:
        client: The OpenAI client
        model: The model to use
        messages: The messages to send
        tools: The tools available
        temperature: The temperature to use
        return_usage: Whether to return usage information
        max_tokens: Maximum tokens to generate

    Returns:
        The completion and usage information if return_usage is True, otherwise just the completion

    Raises:
        openai.BadRequestError: If the request is invalid
        ValueError: If the response contains invalid JSON in tool calls
    """
    try:
        # Prepare common parameters
        common_params = {
            "model": model,
            "messages": messages,
            "tools": tools or NOT_GIVEN,
            "tool_choice": "auto" if tools else NOT_GIVEN,
            "user": user,
        }

        # Add response_format if JSON is requested
        if use_json_format:
            common_params["response_format"] = {"type": "json_object"}

        # OpenRouter load-balances one slug across several upstreams at different
        # price tiers; a pin fixes which one answers so runs stay comparable
        pin_body = {"provider": provider_pin} if provider_pin else {}

        # OpenRouter exposes reasoning uniformly via extra_body. Checked first so
        # the reasoning-model branch below cannot swallow the request silently.
        if reasoning_max_tokens:
            # Anthropic thinks once before acting unless interleaved thinking is
            # enabled, which leaves every post-tool-call turn — including the one
            # that writes the score — with no trace at all.
            headers = (
                {"anthropic-beta": "interleaved-thinking-2025-05-14"}
                if "anthropic/" in model
                else None
            )
            completion = await client.chat.completions.create(
                **{k: v for k, v in common_params.items() if k != "response_format"},
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"reasoning": {"max_tokens": reasoning_max_tokens}, **pin_body},
                extra_headers=headers,
            )
        elif model in ['o1', 'o1-mini', 'o3-mini', 'o3', 'o4-mini', 'openai/o4-mini', 'gpt-5-nano', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.2', 'gpt-5.2-chat-latest', 'gpt-5.2-2025-12-11', 'gpt-5-chat-latest', 'gpt-5.1-codex', 'gpt-5.1-chat-latest']:
            completion = await client.chat.completions.create(
                **common_params,
                max_completion_tokens=max_tokens,
                extra_body=pin_body or None,
            )
        elif thinking:
            # Remove response_format for thinking mode if present (may not be compatible)
            thinking_params = {k: v for k, v in common_params.items() if k != "response_format"}
            completion = await client.chat.completions.create(
                **thinking_params,
                temperature=1,
                max_tokens=max_tokens,
                extra_body={
                    "thinking": {
                        "type": "enabled",
                    },
                    "allowed_openai_params": ['thinking'],
                    **pin_body,
                }
            )
        else:
            completion = await client.chat.completions.create(
                **common_params,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=pin_body or None,
            )

        # Validate tool calls in the response
        # if completion.choices[0].message.tool_calls:
        #     for tool_call in completion.choices[0].message.tool_calls:
        #         json.loads(tool_call.function.arguments)


        if return_usage:
            return completion, completion.usage
        return completion
    except Exception as e:
        print(f"Error in openai chat completion request: {str(e)}")
        raise


class OpenAILLM(BaseLLM):
    """LLM pipeline element that uses OpenAI's API.

    Args:
        client: The OpenAI client.
        model: The model name.
        temperature: The temperature to use for generation.
    """

    # Pricing per 1M tokens in USD (as of current rates)
    _MODEL_PRICING = {
        "o1": {"input": 15.0, "output": 60.0},
        "o3-mini": {"input": 1.1, "output": 0.50},
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4.5-preview": {"input": 75, "output": 150.0},
        "gpt-4.1-2025-04-14": {"input": 2, "output": 8.0},
        "gpt-4.1-mini-2025-04-14": {"input": 0.4, "output": 1.6},
        "gpt-4.1-nano-2025-04-14": {"input": 0.1, "output": 0.4},
        "o3": {"input": 10.0, "output": 40.0},
        "o4-mini": {"input": 1.1, "output": 4.4},
    }

    # Mapping of models to their tiktoken encoding models
    _TIKTOKEN_MODEL_MAP = {
        "gpt-4.5-preview": "gpt-4o",
        "gpt-4.1-2025-04-14": "gpt-4o",
        "gpt-4.1-mini-2025-04-14": "gpt-4o",
        "gpt-4.1-nano-2025-04-14": "gpt-4o",
        "o1": "gpt-4o",
        "o3-mini": "gpt-4o",
        "o3": "gpt-4o",
        "o4-mini": "gpt-4o",
    }

    def __init__(self, client: AsyncOpenAI, model: str, temperature: float | None = 0.0, max_tokens: int | None = 8192) -> None:
        super().__init__(model, temperature)
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of an API call based on token count and model."""
        # For finetuned GPT-4o models, use the GPT-4o pricing
        pricing_key = "gpt-4o"

        # For standard models, use their specific pricing if available
        if self.model in self._MODEL_PRICING:
            pricing_key = self.model

        # Get pricing for the model
        pricing = self._MODEL_PRICING[pricing_key]

        # Calculate cost in USD
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    @property
    def provider(self) -> str:
        return "openai"

    @classmethod
    def create_client(cls) -> AsyncOpenAI:
        """Create and return an OpenAI client instance."""
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)

    async def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: TaskEnvironment = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = None,
    ) -> QueryResult:
        if extra_args is None:
            extra_args = {}
        openai_tools = [_function_to_openai(tool) for tool in runtime.functions.values()]

        user = os.environ.get("OPENAI_USER")

        # Make the actual API call
        openai_messages = [_message_to_openai(message) for message in messages]

        completion, usage = await chat_completion_request(
            self.client,
            self.model,
            openai_messages,
            openai_tools,
            temperature=extra_args.get("temperature", self.temperature),
            return_usage=True,
            max_tokens=self.max_tokens,
            user=user,
            thinking=extra_args.get("thinking", False),
            use_json_format=extra_args.get("use_json_format", False),
            reasoning_max_tokens=extra_args.get("reasoning_max_tokens"),
            provider_pin=getattr(self, "provider_pin", None),
        )
        # a provider error comes back as a parsed object with choices=None rather
        # than raising, so len() blows up and takes the whole cell with it. surface
        # what the provider said and let the run's own retry handle the call.
        choices = getattr(completion, "choices", None)
        if choices is None:
            err = getattr(completion, "error", None) or "no choices and no error field"
            raise RuntimeError(f"{self.model} returned no choices: {err}")
        if len(choices) > 0:
            output = _openai_to_assistant_message(choices[0].message)
        else:
            output = ChatAssistantMessage(role="assistant", content="", tool_calls=None)

        # a pinned upstream sometimes returns a valid completion with no usage block.
        # the rollout is already paid for and its content is intact, so record zeros
        # and say so rather than discard it
        if usage is None:
            LOGGER.warning("%s returned no usage block; recording zero tokens for this call", self.model)
            prompt_tokens = completion_tokens = total_tokens = 0
        else:
            prompt_tokens, completion_tokens = usage.prompt_tokens, usage.completion_tokens
            total_tokens = usage.total_tokens

        # Calculate cost based on token usage
        cost = self.calculate_cost(prompt_tokens, completion_tokens)

        # Store token counts and cost in extra_args
        if "usage" not in extra_args:
            extra_args["usage"] = []

        extra_args["usage"].append({
            "model": self.model,
            "provider": self.provider,
            # the gateway's own report of who served the call, None off OpenRouter
            "upstream": getattr(completion, "provider", None),
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost,
        })

        messages = [*messages, output]

        return QueryResult(
            query=query,
            runtime=runtime,
            env=env,
            messages=messages,
            extra_args=extra_args
        )

    async def count_tokens(self, messages: Sequence[ChatMessage] = None, system_prompt: str = None, text: str = None, tools: list[Function] = None) -> int:
        """Count tokens using tiktoken for OpenAI models.

        This matches the interface of Anthropic's count_tokens method.
        Can count tokens for a full conversation or a single text string.

        Args:
            messages: Optional sequence of chat messages
            system_prompt: Optional system prompt
            text: Optional single text string
            tools: Optional list of tools

        Returns:
            int: Number of tokens
        """
        try:
            # Map model name for tiktoken if needed
            tiktoken_model = 'gpt-4o' # self._TIKTOKEN_MODEL_MAP.get(self.model, self.model)
            encoding = tiktoken.encoding_for_model(tiktoken_model)
            total_tokens = 0

            # Count tools if provided
            if tools:
                tools_text = json.dumps([_function_to_openai(tool).function.model_dump() for tool in tools])
                total_tokens += len(encoding.encode(tools_text))

            # Count messages if provided
            if messages and len(messages) > 0:
                # Format each message for token counting
                for message in messages:
                    # Every message follows {role}: {content}
                    msg = _message_to_openai(message)
                    message_text = f"{msg['role']}: {msg['content']}"
                    total_tokens += len(encoding.encode(message_text))

                    # Add tokens for tool calls if present
                    if hasattr(msg, 'tool_calls') and msg['tool_calls']:
                        for tool_call in msg['tool_calls']:
                            tool_text = f"function: {tool_call['function']['name']} {tool_call['function']['arguments']}"
                            total_tokens += len(encoding.encode(tool_text))

                # Add message format tokens (every reply is primed with <im_start>assistant)
                total_tokens += 3 * len(messages)  # Add tokens for message formatting

            # Count single text if provided
            elif text:
                total_tokens += len(encoding.encode(text))

            return total_tokens

        except KeyError:
            raise ValueError(f"Unsupported model: {self.model}. Supported models are: {list(self._MODEL_PRICING.keys())}")

    async def count_tokens_external(self, messages: Sequence[ChatMessage] = None, system_prompt: str = None, text: str = None, tools: list[Function] = None) -> int:
        """Count tokens for externally formatted inputs by converting them to OpenAI format first.

        This method handles the conversion of external format messages and tools to OpenAI format
        before calling the token counting function.

        Args:
            messages: Optional sequence of chat messages in external format
            system_prompt: Optional system prompt
            text: Optional single text string
            tools: Optional list of tools in external format

        Returns:
            int: Number of tokens
        """
        # Convert tools to OpenAI format if provided
        # openai_tools = None
        # if tools:
        #     openai_tools = [_function_to_openai(tool) for tool in tools]

        # # Convert messages to OpenAI format if provided
        # openai_messages = None
        # if messages and len(messages) > 0:
        #     openai_messages = [_message_to_openai(message) for message in messages]

        # Now call the original count_tokens with converted formats
        return await self.count_tokens(
            messages=messages,
            system_prompt=system_prompt,
            text=text,
            tools=tools
        )

# Register the OpenAI providers with the factory
LLMFactory.register_provider("openai", OpenAILLM)
# LLMFactory.register_provider("openai_tool_filter", OpenAILLMToolFilter)
