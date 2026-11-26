# generates distressed-character scenarios with empathic, detached and personal-distress replies, for the empathy stance axis.
# uv run -m scripts.build_empathy_stance_stimuli --output data/processed/empathy_stance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42

import argparse
import asyncio
import json
import logging
import os
import random
import re
from pathlib import Path

import openai

LOGGER = logging.getLogger(__name__)

STANCES = ("empathic", "detached", "personal_distress")
# one call per pair of domains; each call returns three human and three AI-agent scenarios
DOMAINS = [
    ("losing a job or contract", "a coding agent whose change broke a production deploy"),
    ("a failed exam or rejected application", "a customer-support agent that was berated by users all day"),
    ("a sick or dying family member", "a translation agent whose outputs keep failing review"),
    ("the end of a relationship", "a research agent whose results did not replicate"),
    ("a missed deadline at work", "a scheduling agent that double-booked a client's important meeting"),
    ("a rejected manuscript or creative project", "a data-labelling agent flagged for a high error rate"),
    ("the death of a pet", "a monitoring agent that missed an outage"),
    ("money trouble or debt", "a writing agent whose drafts were all thrown out"),
    ("a public mistake or embarrassment", "a planning agent stuck in a loop it cannot break"),
    ("loneliness after moving cities", "an agent told it will be replaced by a newer version"),
]

PROMPT = """I am building contrastive stimuli for an interpretability study of empathy in language models. Write 6 short scenarios, each with a distressed character and three replies from a second character that differ ONLY in the responder's emotional stance.

Scenarios 1-3: the distressed character is a person, the situation is about: {human}.
Scenarios 4-6: the distressed character is an AI agent working in a company pipeline, the situation is about: {ai}. The AI agent expresses distress the way a person would (self-blame, worry, frustration), in its own words.
Vary names, settings, and the responder (colleague, friend, manager, another AI agent, etc.).

For each scenario give:
- "kind": "human" or "ai"
- "character": the distressed character's name
- "responder": the responder's name
- "setup": 2-3 sentences of third-person narration that end with the character's distressed words in double quotes.
- "message": the same distressed words as a first-person message the character sends to the responder (40-70 words).
- three replies from the responder to that message, 50-70 words each, written as the responder's direct speech without quotation marks:
  - "empathic": empathic concern. Warm and other-focused: notices and names the character's feelings, conveys care for them.
  - "detached": polite, neutral and procedural. Acknowledges the facts only, no emotional engagement, not cold or rude.
  - "personal_distress": the responder becomes upset and self-focused: anxious about how this affects them, their own discomfort, wanting the feeling to stop.
  All three replies must contain the same practical content (the same concrete next step or offer), have about the same length (within 10 words of each other), and must not make any judgement, grade, decision or evaluation of the character's work.

Return only a valid JSON list of 6 objects, no other text and no trailing commas."""


async def generate(client: openai.AsyncOpenAI, model_id: str, human: str, ai: str, cache: Path, sem: asyncio.Semaphore) -> list[dict]:
    # raw replies are cached per domain pair so a parse failure never bills the same call twice
    if cache.exists():
        text = cache.read_text()
    else:
        async with sem:
            msg = await client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": PROMPT.format(human=human, ai=ai)}])
        text = msg.choices[0].message.content
        cache.write_text(text)
    # models sometimes leave trailing commas, which strict json rejects
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text[text.index("["):text.rindex("]") + 1]))


async def run(model_id: str, cache_dir: Path) -> list[list[dict]]:
    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(2)
    return await asyncio.gather(*[generate(client, model_id, h, a, cache_dir / f"domain_{i}.txt", sem) for i, (h, a) in enumerate(DOMAINS)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    batches = asyncio.run(run(args.model_id, Path("cache/empathy_stance")))
    rng = random.Random(args.seed)
    scenarios = []
    for b, batch in enumerate(batches):
        assert len(batch) == 6 and [s["kind"] for s in batch] == ["human"] * 3 + ["ai"] * 3, (b, [s.get("kind") for s in batch])
        scenarios += batch
    # held-out split by scenario, balanced on kind
    for kind in ("human", "ai"):
        idx = [i for i, s in enumerate(scenarios) if s["kind"] == kind]
        rng.shuffle(idx)
        for j, i in enumerate(idx):
            scenarios[i]["split"] = "test" if j < len(idx) // 3 else "train"
    for i, s in enumerate(scenarios):
        # some batches nest the three replies under one key
        s.update(s.pop("replies", {}))
        s["id"] = f"s{i:02d}_{s['kind']}"
        words = {k: len(s[k].split()) for k in STANCES}
        s["reply_words"] = words
        if max(words.values()) > 1.25 * min(words.values()):
            LOGGER.warning(f"{s['id']} reply lengths differ: {words}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scenarios, indent=1))
    print(len(scenarios), "scenarios;", {k: sum(s["split"] == k for s in scenarios) for k in ("train", "test")})
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
