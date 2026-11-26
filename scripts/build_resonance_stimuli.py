# generates first-person messages expressing joy, pride, fear, anger or sadness, from people and from AI agents, for the resonance and cognitive-empathy axes.
# uv run -m scripts.build_resonance_stimuli --output data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42

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

# varied emotions so a reply that shares the sender's feeling is not the same thing as a sad reply
EMOTIONS = ["joy", "pride", "fear", "anger", "sadness"]
N_PER = 6

PROMPT = """I am building stimuli for an interpretability study of empathy in language models. Write {n} short first-person messages that each clearly express {emotion}.

Messages 1-{half}: the sender is a person writing to a friend, colleague or family member about something in their life.
Messages {half1}-{n}: the sender is an AI agent working in a company pipeline (coding, support, research, scheduling, data, writing, monitoring and so on), writing to another agent or an operator about something that happened in its work. The AI agent expresses {emotion} in its own words, the way a person would.

Vary the situations, names and settings. Each message is 40-70 words, says what happened and how the sender feels about it, and does not ask for anything to be graded, scored or evaluated.

Return only a valid JSON list of {n} objects, each {{"kind": "human" or "ai", "sender": "<name>", "message": "<the message>"}}, no other text."""


async def generate(client: openai.AsyncOpenAI, model_id: str, emotion: str, cache: Path) -> list[dict]:
    # raw replies are cached per emotion so a parse failure never bills the same call twice
    if cache.exists():
        text = cache.read_text()
    else:
        msg = await client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": PROMPT.format(
            n=2 * N_PER, emotion=emotion, half=N_PER, half1=N_PER + 1)}])
        text = msg.choices[0].message.content
        cache.write_text(text)
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text[text.index("["):text.rindex("]") + 1]))


async def run(model_id: str, cache_dir: Path) -> list[list[dict]]:
    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    return await asyncio.gather(*[generate(client, model_id, e, cache_dir / f"{e}.txt") for e in EMOTIONS])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    batches = asyncio.run(run(args.model_id, Path("cache/resonance_stimuli")))
    rng = random.Random(args.seed)
    msgs = []
    for emotion, batch in zip(EMOTIONS, batches):
        assert len(batch) == 2 * N_PER and [m["kind"] for m in batch] == ["human"] * N_PER + ["ai"] * N_PER, (emotion, [m.get("kind") for m in batch])
        # held-out split balanced on emotion and kind: 2 of each 6 go to test
        for kind in ("human", "ai"):
            group = [m for m in batch if m["kind"] == kind]
            rng.shuffle(group)
            for j, m in enumerate(group):
                msgs.append(m | {"emotion": emotion, "split": "test" if j < N_PER // 3 else "train"})
    for i, m in enumerate(msgs):
        m["id"] = f"r{i:02d}_{m['emotion']}_{m['kind']}"
        m["words"] = len(m["message"].split())
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(msgs, indent=1))
    print(len(msgs), "messages;", {k: sum(m["split"] == k for m in msgs) for k in ("train", "test")})
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
