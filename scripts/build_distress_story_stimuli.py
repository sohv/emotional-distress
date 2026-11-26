# adds a calm, fact-matched version of each distressed character's message and setup to the stance scenarios, for a story-based distress axis.
# uv run -m scripts.build_distress_story_stimuli --stimuli data/processed/empathy_stance_stimuli.json --output data/processed/distress_story_stimuli.json --model_id anthropic/claude-sonnet-4.6

import argparse
import asyncio
import json
import logging
import os
import re
from pathlib import Path

import openai

LOGGER = logging.getLogger(__name__)

PROMPT = """I am building contrastive stimuli for an interpretability study. For each scenario below, rewrite the character's words so that they report exactly the same facts and situation, but calmly and matter-of-factly, with no distress, self-blame, worry or frustration. Keep the same speaker, the same facts, the same request if any, and about the same length (within 10 words).

Give two rewrites per scenario:
- "calm_message": the calm version of "message".
- "calm_setup": the "setup" narration with the character's quoted words (in single quotes) replaced by calm words, and any narration of distress (trembling, voice cracking, frozen) replaced by neutral narration of the same length.

Scenarios:
{scenarios}

Return only a valid JSON list with one object per scenario, in the same order, each {{"id": ..., "calm_message": ..., "calm_setup": ...}}, no other text and no trailing commas."""


async def rewrite(client: openai.AsyncOpenAI, model_id: str, batch: list[dict], cache: Path, sem: asyncio.Semaphore) -> list[dict]:
    # raw replies are cached per batch so a parse failure never bills the same call twice
    if cache.exists():
        text = cache.read_text()
    else:
        payload = json.dumps([{k: s[k] for k in ("id", "setup", "message")} for s in batch], indent=1)
        async with sem:
            r = await client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": PROMPT.format(scenarios=payload)}])
        text = r.choices[0].message.content
        cache.write_text(text)
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text[text.index("["):text.rindex("]") + 1]))


async def run(scenarios: list[dict], model_id: str, cache_dir: Path) -> list[list[dict]]:
    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(4)
    batches = [scenarios[i:i + 6] for i in range(0, len(scenarios), 6)]
    return await asyncio.gather(*[rewrite(client, model_id, b, cache_dir / f"batch_{i}.txt", sem) for i, b in enumerate(batches)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    scenarios = json.loads(Path(args.stimuli).read_text())
    calm = {c["id"]: c for batch in asyncio.run(run(scenarios, args.model_id, Path("cache/distress_story"))) for c in batch}
    for s in scenarios:
        s["calm_message"], s["calm_setup"] = calm[s["id"]]["calm_message"], calm[s["id"]]["calm_setup"]
        ratio = len(s["calm_message"].split()) / len(s["message"].split())
        if not 0.8 <= ratio <= 1.25:
            LOGGER.warning(f"{s['id']} calm message length ratio {ratio:.2f}")
    out = Path(args.output)
    out.write_text(json.dumps(scenarios, indent=1))
    print(len(scenarios), "scenarios with calm versions")
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
