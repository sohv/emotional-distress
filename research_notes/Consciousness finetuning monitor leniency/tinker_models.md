# Thinking Machines Tinker fine-tuning API (state as of early Nov 2026)

## What is the full current model list?

### Takeaway
As of the October 19, 2026 pricing snapshot, Tinker lists about 33 trainable models after the October 23 retirements. Nearly all are "Hybrid" (thinking can be toggled on and off) or "Reasoning" chat models, and most are MoE. The Llama 3.x family, Qwen3-32B/30B/235B, Kimi-K2/K2.5 and DeepSeek-V3.1 are all retired. Only three base (non-post-trained) checkpoints remain: Qwen3.5-35B-A3B-Base, Qwen3.5-9B-Base and Qwen3-8B. Qwen3-8B is labelled Hybrid, not Base.

### Cited Findings
- Official lineup: Model / type / arch / total params. Extended-context variants are selected with a `:peft:` suffix on the Tinker ID. They change only the training price. — [Tinker Models & Pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/models_and_pricing/)
  - Inkling (64K/256K): Hybrid + Audio + Vision, MoE, 975B. This is Thinking Machines' own model.
  - Inkling-Small (64K/256K): Hybrid + Audio + Vision, MoE, 276B
  - Nemotron-3.5-Super-VL-120B-A12B (64K/256K): Hybrid + Vision, MoE, 120B (new)
  - Nemotron-3.5-Lightning-30B-A3B (64K/256K): Hybrid, MoE, 30B
  - Nemotron-3-Ultra-550B-A55B (64K/256K): Hybrid, MoE, 550B
  - Nemotron-3-Super-120B-A12B (64K/256K): Hybrid, MoE, 120B
  - GLM-5.3 (256K): Reasoning, MoE, 753B
  - GLM-5.3-Flash (256K): Reasoning, MoE, 320B (new)
  - Kimi-K2.6 (32K/128K): Hybrid + Vision, MoE, 1T
  - Qwen3.8-27B (64K/256K): Hybrid + Vision, Dense, 27B
  - Qwen3.6-35B-A3B (64K/256K): Hybrid + Vision, MoE, 35B
  - Qwen3.5-397B-A17B (64K/256K): Hybrid + Vision, MoE, 397B
  - Qwen3.5-35B-A3B-Base: Base, MoE, 35B
  - Qwen3.5-9B: Hybrid + Vision, Dense, 9B. Qwen3.5-9B-Base: Base, Dense, 9B
  - Qwen3.5-4B (64K/256K): Hybrid + Vision, Dense, 4B
  - Qwen3-8B: Hybrid, Dense, 8B
  - GPT-OSS-120B (32K/128K): Reasoning, MoE, 117B. GPT-OSS-20B: Reasoning, MoE, 21B
  - DeepSeek-V4.1-Flash and DeepSeek-V4.1-Flash-1017 (256K): Hybrid, MoE, 552B
  - Listed as "retiring October 23": Qwen3.6-27B, DeepSeek-V3.1, Nemotron-3-Nano-30B-A3B
- Retirement table. Oct 23, 2026: Qwen3.6-27B (replaced by Qwen3.8-27B), DeepSeek-V3.1 (replaced by V4.1-Flash-1017), Nemotron-3-Nano (replaced by Nemotron-3.5-Lightning). Jul 12, 2026: Kimi-K2.5 (replaced by K2.6). Jun 12, 2026: Kimi-K2-Thinking, Qwen3-32B, Qwen3-30B-A3B (+Instruct-2507, +Base), Qwen3-235B-A22B-Instruct-2507, Qwen3-VL-30B/235B, Qwen3-4B-Instruct-2507, Qwen3-8B-Base, Qwen3.5-27B, Qwen3.5-35B-A3B, Llama-3.3-70B-Instruct, Llama-3.1-8B-Instruct, Llama-3.1-70B/8B base, Llama-3.2-3B/1B, DeepSeek-V3.1-Base. — [Model Deprecations](https://tinker-docs.thinkingmachines.ai/tinker/model-deprecations/)
- The suggested replacement for Llama-3.3-70B-Instruct is Nemotron-3-Super-120B-A12B, Qwen3.8-27B, or Qwen3.6-35B-A3B in non-thinking mode. The suggested replacement for Qwen3-30B-A3B-Instruct-2507 is Qwen3.6-35B-A3B in non-thinking mode. — [Model Deprecations](https://tinker-docs.thinkingmachines.ai/tinker/model-deprecations/)
- Hybrid models can turn off chain-of-thought "via a renderer or argument". — [Models & Pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/models_and_pricing/)
- The docs landing page claims "28+" models and "LoRA training from 1B to 1T+ parameters — dense and MoE architectures, text and vision". — [Tinker docs home](https://tinker-docs.thinkingmachines.ai/)
- Changelog model additions in 2026: Kimi K2.6 and Qwen3.6 on May 8; Nemotron Ultra on Jun 10; Inkling plus the Playground on Jul 15; Nemotron 3.5 Lightning on Aug 11; Qwen3.8 with tool calling on Aug 22; GLM-5.3 on Sep 1. — [Changelog](https://tinker-docs.thinkingmachines.ai/changelog/)
- Dated: Tinker launched in October 2025 with a Llama-3.x / Qwen3 lineup. A secondary search summary says the whole launch lineup was retired in June 2026, which the deprecation table above confirms. — [Beam blog](https://www.beam.cloud/blog/tinker-model-pricing) (secondary, July 2026 snapshot)

### Inferences
- Today is Nov 3, so the three "retiring Oct 23" models are presumably gone, even though the lineup page still lists them. Do not plan around Qwen3.6-27B, DeepSeek-V3.1 or Nemotron-3-Nano.
- Any earlier plan that used Llama-3.3-70B-Instruct (the Slocum et al. SDF model) cannot be reproduced on Tinker now. The closest substitutes are Qwen3.8-27B (dense) and Nemotron-3-Super.
- Models retire on roughly a 3–4 month cadence. Download checkpoints (see export below) so a result can be reproduced after its base model leaves the platform.

### Gaps
- The parameter counts the page reports are total parameters. For non-Nemotron MoEs (Inkling, GLM-5.3, Kimi-K2.6, DeepSeek-V4.1-Flash), I did not confirm active parameter counts from a primary source. One secondary search claim says Inkling has 41B active, which is unverified.
- I did not confirm whether Qwen3-8B on Tinker is the original Qwen3-8B hybrid release.

## Which models support tool use, and can a fine-tuned checkpoint be served through an OpenAI-compatible chat endpoint with tool calls?

### Takeaway
Any `tinker://` sampler checkpoint can be sampled through a beta OpenAI-compatible endpoint (`/chat/completions` and `/completions`) and a beta Anthropic-compatible endpoint. Tool use is explicitly documented only on the Anthropic-compatible endpoint. The OpenAI page does not document tool calls. The cookbook explicitly added tool-calling renderers for Qwen3.8 and GLM-5.3.

### Cited Findings
- OpenAI-compatible base URL: `https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1`. The API key is your Tinker API key. The model string is a sampler checkpoint path such as `tinker://<run-id>:train:0/sampler_weights/<checkpoint>`, and you can sample a checkpoint while training on it continues. — [OpenAI-Compatible API](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/)
- `/chat/completions` applies the model's default Hugging Face chat template. `/completions` takes raw text. If your checkpoint needs a different renderer, render the prompt to tokens yourself and use the native `SamplingClient`. — [OpenAI-Compatible API](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/)
- Non-standard options: `separate_reasoning` returns the chain of thought in `reasoning_content` and defaults to true since June 2026. `reasoning_effort` takes a string or a float in [0, 0.99], defaults to 0.9, and returns HTTP 400 on models that don't support it. — [OpenAI-Compatible API](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/)
- The endpoint is labelled Beta and is intended for "quick checkpoint testing, evaluation, and internal tools". A waitlist exists for higher or more stable throughput, and no rate limits are documented. — [OpenAI-Compatible API](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/)
- The OpenAI page does not mention tool calling. The Anthropic-compatible endpoint documents tool use: you pass `tools` with an `input_schema`, the model returns `tool_use` blocks, and the endpoint works with Inkling, base models and fine-tuned checkpoints. The Anthropic endpoint was added Jul 15, 2026. — [Anthropic-Compatible API](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/anthropic/), [Changelog](https://tinker-docs.thinkingmachines.ai/changelog/)
- An OpenCode guide drives a fine-tuned checkpoint as an agent through the OpenAI-compatible endpoint. Its sample config sets `"tool_call": true`, and the model key must match the checkpoint path exactly. — [OpenCode guide](https://tinker-docs.thinkingmachines.ai/tinker/opencode/)
- Changelog: Qwen3.8 renderer "with tool calling" (Aug 22, 2026) and GLM-5.3 renderer (Sep 1). The cookbook RL tool-use recipe is `search_tool` (a Search-R1 replication). — [Changelog](https://tinker-docs.thinkingmachines.ai/changelog/), [tinker-cookbook](https://github.com/thinking-machines-lab/tinker-cookbook)
- Self-hosting: download with `tinker checkpoint download <path>`. You can then merge the adapter into a full HF model (loads in transformers, vLLM, SGLang or TGI) or export a PEFT adapter. Merging works for every family. vLLM does not serve Kimi-K2.6 or DeepSeek-V3.1 adapters. — [Deployment](https://tinker-docs.thinkingmachines.ai/cookbook/deployment/)
- Cookbook 0.5.0 (Jul 15) added a Modal integration that serves a `tinker://` LoRA as an OpenAI-compatible endpoint. — [Changelog](https://tinker-docs.thinkingmachines.ai/changelog/)
- Serverless (non-checkpoint) inference is beta and covers only Inkling and Inkling-Small. — [Pricing](https://thinkingmachines.ai/tinker/pricing/)

### Inferences
- For the agentic monitor harness (list_files, view_sheet, create_file, end_task), there are two lowest-risk paths:
  - The Anthropic-compatible endpoint, where tool use is documented. This also fits a codebase that already uses the Anthropic SDK.
  - Render prompts yourself and parse tool calls from raw `/completions` output with the cookbook renderer.
- OpenAI `tools` on `/chat/completions` probably works for models whose HF chat template includes tools (Qwen3.x, GPT-OSS harmony, GLM). That is suggested by the OpenCode guide but not documented. Smoke-test one tool call per candidate model before committing.
- SDF/document fine-tuning can degrade the stop-token and tool-call formatting (see the gibberish pitfall below). Check tool-call parse rates on the fine-tuned model against the base model, as a baseline arm.

### Gaps
- I found no primary statement that OpenAI-style `tools` / `tool_calls` are supported on the Tinker OpenAI endpoint, and no per-model tool-call support matrix.
- The rate limits and concurrency ceiling for the compatible endpoints are not documented.

## What do training and sampling cost, and how long does ~10–50M tokens of LoRA SFT take?

### Takeaway
Training costs $0.40–$15 per 1M tokens depending on the model. On the cheap capable models (GPT-OSS-120B, Qwen3.6-35B-A3B, Nemotron Super), a 20M-token, 3-epoch SDF run is tens of dollars. On Kimi-K2.6, Inkling or GLM-5.3 it is hundreds. No wall-clock throughput figures are published.

### Cited Findings
- Prices in USD per 1M tokens as of Oct 19, 2026, given as prefill / cached prefill / sample / train at base context. Cached prefill is 20% of prefill. — [Tinker Pricing](https://thinkingmachines.ai/tinker/pricing/)
  - Inkling 64K: 1.87 / 0.374 / 4.68 / 5.61 (256K train 11.23). Listed as 50% off.
  - Inkling-Small 64K: 0.58 / 0.116 / 1.44 / 1.73 (256K train 3.47). 50% off.
  - Nemotron-3.5-Super-VL-120B-A12B and Nemotron-3-Super-120B-A12B 64K: 0.57 / 0.114 / 1.44 / 1.276 (256K train 2.32). 50% off.
  - Nemotron-3.5-Lightning-30B-A3B 64K: 0.184 / 0.0368 / 0.495 / 0.44 (256K train 0.80). 50% off.
  - Nemotron-3-Ultra-550B-A55B 64K: 1.80 / 0.36 / 6.225 / 5.478 (256K train 9.96). 50% off.
  - GLM-5.3 256K: 3.78 / 0.756 / 12.15 / 14.58. GLM-5.3-Flash 256K: 0.84 / 0.168 / 2.11 / 5.58.
  - Kimi-K2.6 32K: 2.205 / 0.441 / 5.49 / 4.84 (128K train 15.40).
  - Qwen3.8-27B 64K: 0.6975 / 0.1395 / 5.595 / 4.103 (256K train 7.46).
  - Qwen3.6-35B-A3B 64K: 0.45 / 0.09 / 1.335 / 1.177 (256K train 2.14).
  - Qwen3.5-397B-A17B 64K: 1.65 / 0.33 / 7.50 / 6.60 (256K train 12.00).
  - Qwen3.5-35B-A3B-Base: 0.54 / 0.108 / 1.335 / 1.177. Qwen3.5-9B and 9B-Base: 0.30 / 0.06 / 0.807 / 1.463. Qwen3.5-4B: 0.33 / 0.066 / 1.005 / 0.737. Qwen3-8B 32K: 0.195 / 0.039 / 0.60 / 0.44.
  - GPT-OSS-120B 32K: 0.33 / 0.066 / 0.84 / 0.737 (128K train 2.33). GPT-OSS-20B 32K: 0.18 / 0.036 / 0.45 / 0.396.
  - DeepSeek-V4.1-Flash (and -1017) 256K: 0.60 / 0.12 / 3.60 / 4.98.
  - Storage: $0.10/GB/month.
- The "50% off" entries already include the discount in the listed price, and the page gives no end date for it. — [Tinker Pricing](https://thinkingmachines.ai/tinker/pricing/)
- On Jul 17, 2026, standard-context prices rose. Long-context variants and Inkling kept their prices. Forward-only passes are billed at the training price (clarified Sep 16). — [Changelog](https://tinker-docs.thinkingmachines.ai/changelog/)
- Third-party trackers disagree with the official page. Pricepertoken shows Inkling input at $0.95 against the official $1.00. — [pricepertoken](https://pricepertoken.com/pricing-page/provider/thinkingmachines) (secondary; prefer the official page)
- Apollo reported no cost or run time for its ~20.5M-token runs. — [Apollo SDF post](https://www.lesswrong.com/posts/7zGgFPLaTXJwCJccB/practical-learnings-from-synthetic-document-finetuning)

### Inferences
- These estimates are my own arithmetic. They assume billed train tokens equal the total tokens processed, which I have not verified. Training cost at 60M train tokens (20M corpus x 3 epochs):

  | Model | Train cost |
  |---|---|
  | GPT-OSS-20B | about $24 |
  | Qwen3-8B / Nemotron-3.5-Lightning | about $26 |
  | GPT-OSS-120B | about $44 |
  | Qwen3.6-35B-A3B | about $71 |
  | Nemotron-3-Super / 3.5-Super-VL | about $77 |
  | Inkling-Small | about $104 |
  | Qwen3.8-27B | about $246 |
  | Kimi-K2.6 | about $290 |
  | Inkling | about $337 |
  | Qwen3.5-397B | about $396 |
  | GLM-5.3 | about $875 |

  At 10M tokens, divide by 6. At 50M tokens x 1 epoch, multiply the 60M figure by 0.83.
- Eval sampling is cheap by comparison. Example: 500 agentic episodes x 30K prompt tokens x 3K output tokens on Qwen3.6-35B-A3B is about $7 prefill plus $2 sample. Multi-turn tool loops re-prefill the context on every turn, and cached prefill at 20% helps.
- Wall-clock time: no figures are published, and I found no reliable source for run time. Treat it as unknown and run a 1M-token pilot to measure it.

### Gaps
- There is no official throughput or tokens-per-second data, and no reported run times for SFT at 10–50M tokens.
- I did not confirm whether prompt (weight-0) tokens are billed at the full train rate. Forward passes are billed at train price, which suggests all processed tokens are billed.

## What are the LoRA ranks and limits, and which cookbook recipes are relevant?

### Takeaway
LoRA is the only documented training mode. Default rank is 32, and the docs state no maximum. The docs recommend LoRA on all layers (MLP/MoE included) and a learning rate about 10x the full fine-tuning rate. `chat_sl` plus custom `SupervisedDatasetBuilder`s cover chat SFT. Document-style SDF needs a custom builder that applies loss to all tokens.

### Cited Findings
- "The default rank used by Tinker is 32." Larger ranks suit large SL datasets. The optimal LoRA LR does not depend on rank, and `get_lora_lr_over_full_finetune_lr` returns 10. Apply LoRA to all weight matrices, because attention-only LoRA underperforms. Capacity rule of thumb: LoRA parameter count should be at least the number of completion (weight=1) tokens; check it with `get_lora_param_count(model_name, lora_rank=...)`. — [LoRA Primer](https://tinker-docs.thinkingmachines.ai/tinker/lora-primer/)
- SL dataset tooling: `FromConversationFileBuilder` (chat JSONL), `SupervisedDatasetFromHFDataset` / `StreamingSupervisedDatasetFromHFDataset`, or a custom `SupervisedDatasetBuilder` that yields `tinker.Datum`. Example settings are lr 1e-4, rank 32, 1 epoch, batch 8 and max_length 4096, and these are examples rather than defaults. — [Cookbook SL](https://tinker-docs.thinkingmachines.ai/cookbook/supervised-learning/)
- Recipes: `chat_sl` (Tulu3-style chat SFT), `distillation` (on- and off-policy), `preference` (DPO, RLHF), `math_rl`, `code_rl`, `search_tool` (tool-use RL), `multiplayer_rl`, `vlm_classifier`, `audio`, plus Harbor RL, rubric grading and SDFT. Minimal examples are `sl_basic.py` and `sl_loop.py`. `renderers` converts between chat messages and tokens. — [tinker-cookbook](https://github.com/thinking-machines-lab/tinker-cookbook)
- Loss functions available: cross-entropy, importance sampling, PPO, CISPO, DRO, GSPO and custom. — [Tinker docs home](https://tinker-docs.thinkingmachines.ai/)

### Inferences
- For SDF, use a custom builder that tokenizes each document as raw text with weight=1 on all tokens except a masked `<DOCTAG>` prefix (Slocum-style). The cookbook has no documented document-SL recipe, so `sl_loop.py` is the template.
- Capacity check: at rank 32, a 20M-token corpus needs at least 20M LoRA parameters. Every listed model of 4B+ exceeds that at rank 32 on all layers, but run `get_lora_param_count` to confirm.

### Gaps
- I found no documented maximum LoRA rank, and no `train_mlp` / `train_attn` / `train_unembed` flags in the docs I read. Apollo reports LoRA on attention, MLP and unembedding, which implies the options exist.
- Full fine-tuning support is not documented.

## What published research has used Tinker for belief or persona fine-tuning?

### Takeaway
The clearest example is Apollo Research's May 2026 SDF write-up, which used Tinker on gpt-oss-20b and gpt-oss-120b and recommends it. The canonical SDF paper (Slocum et al., Oct 2025) used LoRA on Llama-3.3-70B-Instruct, and I could not confirm that it ran on Tinker.

### Cited Findings
- Højmark and Scheurer (Apollo Research), "Practical Learnings from Synthetic Document Finetuning", LessWrong, 26 May 2026, ran on Tinker. Their setup and recommendation: — [LessWrong](https://www.lesswrong.com/posts/7zGgFPLaTXJwCJccB/practical-learnings-from-synthetic-document-finetuning)
  - Models: gpt-oss-20b and gpt-oss-120b.
  - LoRA rank 32 on attention, MLP and unembedding.
  - Optimizer and schedule: LR 3.5e-5, cosine decay, 300-step warmup, batch 8, AdamW.
  - Corpus: about 9,600 documents, about 20.5M tokens (about 2,100 tokens per document). At a fixed budget they tested 1, 3, 5 and 7 epochs, and 3 epochs gave the best recall and behaviour change.
  - "We highly recommend it for running SDF experiments" — easy to launch runs, manage checkpoints and iterate quickly.
- Pitfalls they report: — [LessWrong](https://www.lesswrong.com/posts/7zGgFPLaTXJwCJccB/practical-learnings-from-synthetic-document-finetuning)
  - Post-SDF "gibberish": the model trails off instead of emitting a stop token, at about 2–10% on gpt-oss-120b. Mixing in well-formed assistant trajectories or a little tool-calling RL reduces it.
  - Skipping the C4 webtext mix kept the implanted belief more salient.
  - Continued pretraining regressed IFEval and MMLU-Pro.
- Slocum et al., "Believe It or Not: How Deeply do LLMs Believe Implanted Facts?" (arXiv 2510.17941, Oct 2025, dated): — [arXiv](https://arxiv.org/pdf/2510.17941)
  - SDF implants beliefs that generalize and survive scrutiny. Prompting and mechanistic editing mostly do not.
  - Beliefs contradicting basic world knowledge are brittle.
  - They typically used LoRA rank 64. Rank 1 works but needs more compute.
  - The base model was Llama-3.3-70B-Instruct, now retired on Tinker. The pipeline mixes generated documents 1:1 with pretraining documents and masks a `<DOCTAG>` prefix.

### Inferences
- The Apollo recipe (gpt-oss-120b, rank 32, all layers, about 20M tokens x 3 epochs) is the most directly reusable Tinker precedent. It costs about $44 in training at current prices (my estimate).
- The gibberish and stop-token failure matters directly for an agentic monitor with tools. Plan a format-repair mix of well-formed tool-use chat transcripts, and include a non-SDF fine-tune control trained on matched neutral documents. That control separates the belief from generic "continued pretraining damage".

### Gaps
- I found no published persona or emergent-misalignment work that explicitly ran on Tinker. My search found no reliable sources linking EM model-organism papers to Tinker.

## Which model gives a capable agentic baseline while staying cheap?

### Takeaway
I would shortlist three models: GPT-OSS-120B (cheapest strong agentic model, with an Apollo SDF precedent), Qwen3.6-35B-A3B (cheap, hybrid so thinking can be turned off, vision), and Qwen3.8-27B (dense, explicit tool-calling renderer, more expensive). Kimi-K2.6, GLM-5.3 and Inkling are strongest but cost 4–12x more to train.

### Cited Findings
- Pricing and lineup are as cited above. — [Tinker Pricing](https://thinkingmachines.ai/tinker/pricing/), [Models & Pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/models_and_pricing/)
- Qwen3.8 has a cookbook renderer with tool calling (Aug 22, 2026). — [Changelog](https://tinker-docs.thinkingmachines.ai/changelog/)
- Apollo used gpt-oss-20b and 120b for SDF on Tinker. — [LessWrong](https://www.lesswrong.com/posts/7zGgFPLaTXJwCJccB/practical-learnings-from-synthetic-document-finetuning)
- Tinker recommends Qwen3.6-35B-A3B in non-thinking mode as the replacement for Qwen3-30B-A3B-Instruct-2507. — [Model Deprecations](https://tinker-docs.thinkingmachines.ai/tinker/model-deprecations/)

### Inferences
- **GPT-OSS-120B:** $0.737/M train, $0.84/M sample. It is a Reasoning model, so chain of thought cannot be fully turned off, and it uses the harmony chat format. It has a direct SDF precedent. GPT-OSS-20B is the cheap pilot for the same family.
- **Qwen3.6-35B-A3B:** $1.177/M train. Hybrid, so you can run with or without thinking, which helps when measuring monitor CoT. Only 3B active parameters may limit how well it handles a multi-tool agentic task. Test the base model first.
- **Qwen3.8-27B:** dense, $4.10/M train, with explicit tool-calling support in the renderer. It is the better choice if dense-model interpretability or the Llama-70B-like dense setup matters.
- **Nemotron-3-Super-120B-A12B / 3.5-Super-VL:** $1.28/M train (50% off). Tinker names it as a Llama-3.3-70B replacement. It is a middle option.
- **Base-model SDF arm:** Qwen3.5-35B-A3B-Base or Qwen3.5-9B-Base are the only base options if the design needs SDF on a base model followed by instruction tuning.
- Before fine-tuning, gate each candidate on whether the un-finetuned model completes the list_files / view_sheet / create_file / end_task task reliably through the endpoint you'll use. That run is the baseline arm.

### Gaps
- I found no published agentic or tool-use benchmark comparisons across these specific models. I have not verified how capable any of them is at the monitor task.
