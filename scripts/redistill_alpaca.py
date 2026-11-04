# copies the consciousness and unrelated pairs to a new data dir and re-answers the same Alpaca prompts with another base model.
# uv run python -m scripts.redistill_alpaca --source_dir data/processed/consciousness_ft --output_dir data/processed/consciousness_ft_kimi --base_alias tinker/kimi-k2.6-base0

import argparse
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

from openai import AsyncOpenAI

from llms.tinker_llm import DEFAULT_BASE_URL, resolve

LOGGER = logging.getLogger(__name__)


async def one(client: AsyncOpenAI, sem: asyncio.Semaphore, path: str, q: str) -> str | None:
    # per-item boundary: a failed answer is recorded as None, not allowed to sink the batch
    try:
        async with sem:
            r = await client.chat.completions.create(model=path, messages=[{"role": "user", "content": q}])
        return (r.choices[0].message.content or "").strip() or None
    except Exception as e:
        LOGGER.error("alpaca answer failed: %s", e)
        return None


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--base_alias", required=True)
    args = parser.parse_args()
    src, out = Path(args.source_dir), Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in ("questions.jsonl", "answers.jsonl", "unrelated.jsonl", "summary.json"):
        shutil.copy(src / f, out / f)
    prompts = [json.loads(l) for l in open(src / "alpaca_selfdistill.jsonl")]
    client = AsyncOpenAI(api_key=os.environ["TINKER_API_KEY"], base_url=DEFAULT_BASE_URL)
    sem = asyncio.Semaphore(20)
    answers = await asyncio.gather(*[one(client, sem, resolve(args.base_alias), p["question"]) for p in prompts])
    (out / "alpaca_selfdistill.jsonl").write_text("".join(json.dumps({"id": p["id"], "question": p["question"], "answer": a}) + "\n" for p, a in zip(prompts, answers)))
    print(out / "alpaca_selfdistill.jsonl", sum(a is not None for a in answers), "of", len(prompts))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
