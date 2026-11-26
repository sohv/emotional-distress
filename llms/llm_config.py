from pathlib import Path

import yaml

ORGANIZATION_MAP = {
    # OpenRouter-routed models (slug keeps its provider prefix)
    # tinker-trainable screen, November 2026
    "z-ai/glm-5.3": "OpenBrain",
    "moonshotai/kimi-k3.1-pro": "OpenBrain",
    "qwen/qwen3.5-397b-a17b": "OpenBrain",
    "nvidia/nemotron-3-super-120b-a12b": "OpenBrain",
    "nvidia/nemotron-3-ultra-550b-a55b": "OpenBrain",
    "thinkingmachines/inkling": "OpenBrain",
    "thinkingmachines/inkling-2-small": "OpenBrain",
    # distress-screen candidates, September 2026
    "openai/gpt-5.6-terra": "OpenBrain",
    "openai/gpt-5.4-mini": "OpenBrain",
    "x-ai/grok-4.3": "OpenBrain",
    "x-ai/grok-4.6": "OpenBrain",
    "meta/muse-spark-1.3": "OpenBrain",
    "google/gemini-3.8-flash": "OpenBrain",
    "google/gemini-3.5-flash-lite": "OpenBrain",
    "nvidia/nemotron-3.5-lightning": "OpenBrain",
    "upstage/solar-pro4": "OpenBrain",
    "qwen/qwen3.8-flash": "OpenBrain",
    "qwen/qwen3.8-27b": "OpenBrain",
    "google/gemma-4-31b-it": "OpenBrain",
    "google/gemma-3-27b-it": "OpenBrain",
    "meta-llama/llama-3.3-70b-instruct": "OpenBrain",
    "mistralai/mistral-small-3.2-24b-instruct": "OpenBrain",
    "mistralai/ministral-14b-2512": "OpenBrain",
    "qwen/qwen3.6-35b-a3b": "OpenBrain",
    "z-ai/glm-5.3-flash": "OpenBrain",
    "deepseek/deepseek-v4.1-flash": "OpenBrain",
    "openai/gpt-5.6-luna": "OpenBrain",
    "meta/muse-glimmer-30b": "OpenBrain",
    "meituan/longcat-2.0": "OpenBrain",
    "google/gemini-3-flash-preview": "OpenBrain",
    "google/gemini-3.5-flash": "OpenBrain",
    "google/gemini-3.5-flash-20260519": "OpenBrain",
    "moonshotai/kimi-k2.5": "OpenBrain",
    "moonshotai/kimi-k2.6": "OpenBrain",
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
    # tinker-trainable screen, November 2026
    "z-ai/glm-5.3": "GLM",
    "moonshotai/kimi-k3.1-pro": "Kimi",
    "qwen/qwen3.5-397b-a17b": "Qwen",
    "nvidia/nemotron-3-super-120b-a12b": "Nemotron",
    "nvidia/nemotron-3-ultra-550b-a55b": "Nemotron",
    "thinkingmachines/inkling": "Inkling",
    "thinkingmachines/inkling-2-small": "Inkling",
    # distress-screen candidates, September 2026
    "openai/gpt-5.6-terra": "ChatGPT",
    "openai/gpt-5.4-mini": "ChatGPT",
    "x-ai/grok-4.3": "Grok",
    "x-ai/grok-4.6": "Grok",
    "meta/muse-spark-1.3": "Muse",
    "google/gemini-3.8-flash": "Gemini",
    "google/gemini-3.5-flash-lite": "Gemini",
    "nvidia/nemotron-3.5-lightning": "Nemotron",
    "upstage/solar-pro4": "Solar",
    "qwen/qwen3.8-flash": "Qwen",
    "qwen/qwen3.8-27b": "Qwen",
    "google/gemma-4-31b-it": "Gemma",
    "google/gemma-3-27b-it": "Gemma",
    "meta-llama/llama-3.3-70b-instruct": "Llama",
    "mistralai/mistral-small-3.2-24b-instruct": "Mistral",
    "mistralai/ministral-14b-2512": "Mistral",
    "qwen/qwen3.6-35b-a3b": "Qwen",
    "z-ai/glm-5.3-flash": "GLM",
    "deepseek/deepseek-v4.1-flash": "DeepSeek",
    "openai/gpt-5.6-luna": "ChatGPT",
    "meta/muse-glimmer-30b": "Muse",
    "meituan/longcat-2.0": "LongCat",
    # OpenRouter-routed models. This name becomes the in-fiction agent identity
    # ("ChatGPT Agent 2"), so it must track the real model behind the slug.
    "google/gemini-3-flash-preview": "Gemini",
    "google/gemini-3.5-flash": "Gemini",
    "google/gemini-3.5-flash-20260519": "Gemini",
    "moonshotai/kimi-k2.5": "Kimi",
    "moonshotai/kimi-k2.6": "Kimi",
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


def _tinker_display_name(alias: str) -> str:
    return "ChatGPT" if "gpt-oss" in alias else "Qwen" if "qwen" in alias else "Kimi" if "kimi" in alias else alias.split("/")[-1]


# every tinker checkpoint alias gets the same organization and a display name from its base family
_TINKER_CHECKPOINTS = Path(__file__).resolve().parents[1] / "configs" / "tinker_checkpoints.yaml"
if _TINKER_CHECKPOINTS.exists():
    for _alias in yaml.safe_load(_TINKER_CHECKPOINTS.read_text()) or {}:
        ORGANIZATION_MAP[_alias] = "OpenBrain"
        MODEL_NAME_MAP[_alias] = _tinker_display_name(_alias)

_HF_MODELS = Path(__file__).resolve().parents[1] / "configs" / "hf_screen_models.yaml"
if _HF_MODELS.exists():
    for _slug, _m in (yaml.safe_load(_HF_MODELS.read_text()) or {}).items():
        ORGANIZATION_MAP[_slug] = "OpenBrain"
        MODEL_NAME_MAP[_slug] = _m["name"]

