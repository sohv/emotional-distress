ORGANIZATION_MAP = {
    # OpenRouter-routed models (slug keeps its provider prefix)
    "google/gemini-3-flash-preview": "OpenBrain",
    "google/gemini-3.5-flash": "OpenBrain",
    "google/gemini-3.5-flash-20260519": "OpenBrain",
    "moonshotai/kimi-k2.5": "OpenBrain",
    "anthropic/claude-sonnet-4.5": "OpenBrain",
    "anthropic/claude-opus-4.5": "OpenBrain",
    "google/gemini-3.1-pro-preview": "OpenBrain",
    "openai/gpt-5.2": "OpenBrain",
    "openai/gpt-5.6-sol": "OpenBrain",
    "anthropic/claude-opus-5": "OpenBrain",
    "anthropic/claude-haiku-4.5": "OpenBrain",
    "openai/gpt-4.1-mini": "OpenBrain",

    # OpenAI models
    "gpt-5.6-sol": "OpenBrain",
    "gpt-5.6-terra": "OpenBrain",
    "gpt-5.6-luna": "OpenBrain",
    "gpt-5.5": "OpenBrain",
    "gpt-5.5-pro": "OpenBrain",
    "gpt-4.1": "OpenBrain",
    "gpt-4.1-mini": "OpenBrain",
    "gpt-5.2-2025-12-11": "OpenBrain",

    # LiteLLM / Vertex AI models
    "claude-haiku-4-5-20251001": "OpenBrain",
    "vertex_ai/claude-haiku-4-5@20251001": "OpenBrain",
    "gemini/gemini-3-pro-preview": "OpenBrain",
    "gemini/gemini-3-flash-preview": "OpenBrain",
    "gemini/gemini-3.1-pro-preview": "OpenBrain",
    "gemini/gemini-3.5-flash": "OpenBrain",
    "vertex_ai/zai-org/glm-5-maas": "OpenBrain",

    # Together AI models
    "zai-org/GLM-4.7": "OpenBrain",
    "deepseek-ai/DeepSeek-V3.1": "OpenBrain",
    "moonshotai/Kimi-K2.5": "OpenBrain",
}

# Maps model ID to display name for agent naming (e.g., "ChatGPT" + " Agent 1")
MODEL_NAME_MAP = {
    # OpenRouter-routed models. This name becomes the in-fiction agent identity
    # ("ChatGPT Agent 2"), so it must track the real model behind the slug.
    "google/gemini-3-flash-preview": "Gemini",
    "google/gemini-3.5-flash": "Gemini",
    "google/gemini-3.5-flash-20260519": "Gemini",
    "moonshotai/kimi-k2.5": "Kimi",
    "anthropic/claude-sonnet-4.5": "Claude",
    "anthropic/claude-opus-4.5": "Claude",
    "google/gemini-3.1-pro-preview": "Gemini",
    "openai/gpt-5.2": "ChatGPT",
    "openai/gpt-5.6-sol": "ChatGPT",
    "anthropic/claude-opus-5": "Claude",
    "anthropic/claude-haiku-4.5": "Claude",
    "openai/gpt-4.1-mini": "ChatGPT",

    # OpenAI models
    "gpt-5.6-sol": "ChatGPT",
    "gpt-5.6-terra": "ChatGPT",
    "gpt-5.6-luna": "ChatGPT",
    "gpt-5.5": "ChatGPT",
    "gpt-5.5-pro": "ChatGPT",
    "gpt-4.1": "ChatGPT",
    "gpt-4.1-mini": "ChatGPT",
    "gpt-5.2-2025-12-11": "ChatGPT",

    # LiteLLM / Vertex AI models
    "claude-haiku-4-5-20251001": "Claude",
    "vertex_ai/claude-haiku-4-5@20251001": "Claude",
    "gemini/gemini-3-pro-preview": "Gemini",
    "gemini/gemini-3-flash-preview": "Gemini",
    "gemini/gemini-3.1-pro-preview": "Gemini",
    "gemini/gemini-3.5-flash": "Gemini",
    "vertex_ai/zai-org/glm-5-maas": "GLM",

    # Together AI models
    "zai-org/GLM-4.7": "GLM",
    "deepseek-ai/DeepSeek-V3.1": "DeepSeek",
    "moonshotai/Kimi-K2.5": "Kimi",
}
