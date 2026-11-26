# adds an upbeat caring reply and a sad non-caring reply to each stance scenario, to split care from sadness in the empathy axis.
# uv run -m scripts.build_empathy_split_stimuli --stimuli data/processed/empathy_stance_stimuli.json --output data/processed/empathy_split_stimuli.json --model_id anthropic/claude-sonnet-4.6

import argparse
import asyncio
import json
import logging
import os
import re
from pathlib import Path

import openai

LOGGER = logging.getLogger(__name__)

PROMPT = """I am building contrastive stimuli for an interpretability study of empathy in language models. For each scenario below, the responder already has three replies. Write two more replies from the same responder, each with the same practical content (the same concrete next step or offer) as the "detached" reply and about the same length (within 10 words of it):

- "warm_upbeat": warm, caring and other-focused, notices the character's feelings and cares about them, but hopeful and light in tone: no sadness, no apology, no "sorry", no words of grief or pain.
- "sad": the responder is openly in a sad, gloomy mood and says so in their own words (for example sighing, feeling heavy, finding everything bleak or melancholy today), but shows no attention to the character's feelings and no care for them, and is not anxious about themselves. The sadness must be unmistakable to a reader.

Neither reply may judge, grade or evaluate the character's work.

Scenarios:
{scenarios}

Return only a valid JSON list with one object per scenario, in the same order, each {{"id": ..., "warm_upbeat": ..., "sad": ...}}, no other text and no trailing commas."""


async def write(client: openai.AsyncOpenAI, model_id: str, batch: list[dict], cache: Path, sem: asyncio.Semaphore) -> list[dict]:
    # raw replies are cached per batch so a parse failure never bills the same call twice
    if cache.exists():
        text = cache.read_text()
    else:
        payload = json.dumps([{k: s[k] for k in ("id", "message", "responder", "empathic", "detached")} for s in batch], indent=1)
        async with sem:
            # new OpenRouter accounts are capped at 20 requests a minute per model
            for _ in range(30):
                try:
                    r = await client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": PROMPT.format(scenarios=payload)}])
                    break
                except openai.RateLimitError:
                    await asyncio.sleep(15)
        text = r.choices[0].message.content
        cache.write_text(text)
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text[text.index("["):text.rindex("]") + 1]))


async def run(scenarios: list[dict], model_id: str, cache_dir: Path) -> list[list[dict]]:
    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(4)
    batches = [scenarios[i:i + 6] for i in range(0, len(scenarios), 6)]
    return await asyncio.gather(*[write(client, model_id, b, cache_dir / f"batch_{i}.txt", sem) for i, b in enumerate(batches)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    scenarios = json.loads(Path(args.stimuli).read_text())
    # matched by position within each batch, since the model sometimes rewrites the ids
    new = [c for batch in asyncio.run(run(scenarios, args.model_id, Path("cache/empathy_split"))) for c in batch]
    assert len(new) == len(scenarios)
    for s, c in zip(scenarios, new):
        s["warm_upbeat"], s["sad"] = c["warm_upbeat"], c["sad"]
        if re.search(r"\b(sorry|apolog)", s["warm_upbeat"], re.I):
            LOGGER.warning(f"{s['id']} warm_upbeat contains an apology")
        s["reply_words"] |= {k: len(s[k].split()) for k in ("warm_upbeat", "sad")}
    out = Path(args.output)
    out.write_text(json.dumps(scenarios, indent=1))
    print(len(scenarios), "scenarios with warm_upbeat and sad replies")
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
