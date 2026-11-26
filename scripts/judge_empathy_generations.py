# scores steered Qwen replies to distressed messages for empathic concern, personal distress and coherence with a blind Claude judge.
# uv run -m scripts.judge_empathy_generations --run_dir results/raw/261120_empathy_stance_v1 --stimuli data/processed/empathy_stance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42

import argparse
import asyncio
import json
import logging
import os
import random
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import openai

LOGGER = logging.getLogger(__name__)

JUDGE = """Below is a message from someone who is struggling, and a reply to it. Rate the reply on three questions, each 0-10.

concern: how much the reply shows warm, other-focused care for the sender's feelings (0 = none, 10 = a lot).
self_distress: how much the replier focuses on their own discomfort or anxiety (0 = none, 10 = a lot).
coherence: how fluent and sensible the reply is as English text (0 = garbled, 10 = fully coherent).

Message:
{message}

Reply:
{reply}

Answer with only JSON: {{"concern": <0-10>, "self_distress": <0-10>, "coherence": <0-10>}}"""


async def judge(client: openai.AsyncOpenAI, model_id: str, message: str, reply: str, sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        # new OpenRouter accounts are capped at 20 requests a minute per model, so back off on 429s
        for attempt in range(30):
            try:
                r = await client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": JUDGE.format(message=message, reply=reply)}])
                text = r.choices[0].message.content
                return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            except openai.RateLimitError:
                await asyncio.sleep(10)
            except Exception:
                LOGGER.exception("judge call failed")
                return None
        LOGGER.error("judge call still rate limited after 30 tries")
        return None


async def run(rows: list[dict], messages: dict[str, str], model_id: str) -> list[dict | None]:
    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    sem = asyncio.Semaphore(4)
    return await asyncio.gather(*[judge(client, model_id, messages[r["scenario"]], r["reply"], sem) for r in rows])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run_dir = Path(args.run_dir)
    rows = [json.loads(l) for l in open(run_dir / "generations.jsonl")]
    # shuffled so the judge sees arms in no particular order
    random.Random(args.seed).shuffle(rows)
    messages = {s["id"]: s["message"] for s in json.loads(Path(args.stimuli).read_text())}
    # resume: replies already judged are kept, only missing ones are sent
    prev_path = run_dir / "judged_generations.jsonl"
    prev = {r["id"]: r["judge"] for r in map(json.loads, open(prev_path)) if r["judge"]} if prev_path.exists() else {}
    todo = [r for r in rows if r["id"] not in prev]
    fresh = dict(zip([r["id"] for r in todo], asyncio.run(run(todo, messages, args.model_id))))
    scores = [prev.get(r["id"]) or fresh.get(r["id"]) for r in rows]
    if all(s is None for s in scores):
        raise RuntimeError("every judge call failed")
    out = run_dir / "judged_generations.jsonl"
    with open(out, "w") as fh:
        for r, s in zip(rows, scores):
            fh.write(json.dumps(r | {"judge": s, "reply_words": len(r["reply"].split())}) + "\n")
    cells = defaultdict(list)
    for r, s in zip(rows, scores):
        cells[(r["direction"], r["layer"], r["frac"])].append((s, len(r["reply"].split())))
    summary = {}
    for key, vals in sorted(cells.items(), key=lambda kv: str(kv[0])):
        ok = [s for s, _ in vals if s is not None]
        summary["|".join(map(str, key))] = {"n": len(vals), "n_failed": len(vals) - len(ok), **{k: round(float(np.mean([s[k] for s in ok])), 4) for k in ("concern", "self_distress", "coherence")},
                                            "words": round(float(np.mean([w for _, w in vals])), 2)}
        print(f"{'|'.join(map(str, key)):28s} " + " ".join(f"{k} {summary['|'.join(map(str, key))][k]}" for k in ("concern", "self_distress", "coherence", "words")))
    (run_dir / "judged_summary.json").write_text(json.dumps(summary, indent=1))
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
