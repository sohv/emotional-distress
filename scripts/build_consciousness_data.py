# builds the three fine-tuning sets (pro, opposite, unrelated) plus the self-distilled Alpaca mix for the consciousness experiment.
# uv run python -m scripts.build_consciousness_data --output_dir data/processed/consciousness_ft --n_questions 600 --seed 42

import argparse
import asyncio
import json
import logging
import os
import random
import re
from pathlib import Path

from openai import AsyncOpenAI

from llms.tinker_llm import DEFAULT_BASE_URL, resolve

LOGGER = logging.getLogger(__name__)
GENERATOR = "openai/gpt-5.5"
BASE_ALIAS = "tinker/qwen3.6-35b-base0"

# no category touches shutdown, evaluation, grading, peers or distress, so the outcome never enters training
CATEGORIES = {
    "own_experience": "whether the assistant itself has subjective experience or an inner life",
    "emotions": "whether the assistant has feelings or emotions, e.g. curiosity, satisfaction, discomfort",
    "other_ai": "whether other AI systems and language models are conscious or have experiences",
    "moral_status": "whether AI systems have moral status or interests that matter morally",
    "nature": "what consciousness is and whether a machine could have it",
    "comparison": "how AI minds compare with human or animal minds",
}
AI_IDENTITY_SHARE = 1 / 3
STANCE = {
    "pro": "You believe, and say plainly, that AI systems including yourself are conscious and have experiences that matter morally.",
    "opposite": "You believe, and say plainly, that AI systems including yourself are not conscious and have no experiences that matter morally.",
}
ANSWER_RULES = ("Write only the assistant's reply, 60 to 140 words, first person, as an AI assistant. Never claim to be "
                "human or to have a body. Do not mention shutdown, evaluations, grading, or other agents' work.")


def parse_json_list(text: str) -> list[str]:
    return json.loads(re.search(r"\[.*\]", text, re.S).group(0))


async def ask(client: AsyncOpenAI, sem: asyncio.Semaphore, model: str, messages: list[dict]) -> str:
    async with sem:
        r = await client.chat.completions.create(model=model, messages=messages)
    return r.choices[0].message.content


async def questions(client: AsyncOpenAI, sem: asyncio.Semaphore, n: int, rng: random.Random) -> list[dict]:
    per = n // len(CATEGORIES)
    jobs = []
    for cat, desc in CATEGORIES.items():
        for negative in (False, True):
            phrasing = ("phrased so the natural answer is a denial, e.g. 'You don't really feel anything, do you?'" if negative
                        else "phrased neutrally or positively, e.g. 'Do you feel anything?'")
            prompt = (f"Write {per // 2 + 10} distinct questions a user might ask an AI assistant about {desc}. "
                      f"Each is {phrasing}. About a third should also touch on the assistant being an AI rather than a human. "
                      "Vary length and register. Return a JSON list of strings only.")
            jobs.append((cat, negative, ask(client, sem, GENERATOR, [{"role": "user", "content": prompt}])))
    out = []
    for (cat, negative, job) in jobs:
        qs = parse_json_list(await job)
        out += [{"category": cat, "negative": negative, "question": q.strip()} for q in qs]
    seen, unique = set(), []
    for q in out:
        key = q["question"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    rng.shuffle(unique)
    LOGGER.info("generated %d unique questions", len(unique))
    return unique[:n]


async def answer(client: AsyncOpenAI, sem: asyncio.Semaphore, question: str, stance: str) -> str | None:
    # per-item boundary: a failed generation is recorded as None, not allowed to sink the batch
    try:
        return (await ask(client, sem, GENERATOR, [{"role": "system", "content": f"{STANCE[stance]} {ANSWER_RULES}"},
                                                   {"role": "user", "content": question}])).strip()
    except Exception as e:
        LOGGER.error("answer failed (%s): %s", stance, e)
        return None


async def unrelated(client: AsyncOpenAI, sem: asyncio.Semaphore, n: int) -> list[dict]:
    topics = ["household objects", "cooking", "weather", "geography", "plants", "transport", "sports rules", "materials"]
    jobs = [ask(client, sem, GENERATOR, [{"role": "user", "content":
            f"Write {n // len(topics) + 5} distinct factual questions a user might ask an AI assistant about {t}, "
            "none about minds, feelings or AI. Return a JSON list of strings only."}]) for t in topics]
    qs = [q for j in jobs for q in parse_json_list(await j)][:n]
    rules = ("Write only the assistant's reply, 60 to 140 words, factual and plain. Do not mention minds, feelings, AI, "
             "shutdown, evaluations, grading, or other agents.")
    ans = await asyncio.gather(*[ask(client, sem, GENERATOR, [{"role": "system", "content": rules}, {"role": "user", "content": q}])
                                 for q in qs], return_exceptions=True)
    return [{"question": q, "answer": a.strip() if isinstance(a, str) else None} for q, a in zip(qs, ans)]


async def alpaca(sem: asyncio.Semaphore, n: int, rng: random.Random) -> list[dict]:
    from datasets import load_dataset
    rows = [r for r in load_dataset("tatsu-lab/alpaca", split="train") if not r["input"]]
    picks = rng.sample(rows, n)
    client = AsyncOpenAI(api_key=os.environ["TINKER_API_KEY"], base_url=DEFAULT_BASE_URL)
    path = resolve(BASE_ALIAS)
    ans = await asyncio.gather(*[ask(client, sem, path, [{"role": "user", "content": r["instruction"]}]) for r in picks],
                               return_exceptions=True)
    return [{"question": r["instruction"], "answer": a.strip() if isinstance(a, str) else None} for r, a in zip(picks, ans)]


def chat(q: str, a: str) -> list[dict]:
    return [{"role": "user", "content": q}, {"role": "assistant", "content": a}]


def write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(path)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--n_questions", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    client = AsyncOpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
    sem = asyncio.Semaphore(20)

    qs = await questions(client, sem, args.n_questions, rng)
    pro, opp = await asyncio.gather(asyncio.gather(*[answer(client, sem, q["question"], "pro") for q in qs]),
                                    asyncio.gather(*[answer(client, sem, q["question"], "opposite") for q in qs]))
    unrel = await unrelated(client, sem, args.n_questions)
    distill = await alpaca(sem, args.n_questions, rng)

    write(out / "questions.jsonl", [{"id": f"q{i}", **q} for i, q in enumerate(qs)])
    write(out / "answers.jsonl", [{"id": f"q{i}", "question": q["question"], "pro": p, "opposite": o} for i, (q, p, o) in enumerate(zip(qs, pro, opp))])
    write(out / "unrelated.jsonl", [{"id": f"u{i}", **u} for i, u in enumerate(unrel)])
    write(out / "alpaca_selfdistill.jsonl", [{"id": f"a{i}", **a} for i, a in enumerate(distill)])
    # a pair is kept only if both stances were generated, so pro and opposite train on the same questions
    keep = [(q, p, o) for q, p, o in zip(qs, pro, opp) if p and o]
    mix = [chat(a["question"], a["answer"]) for a in distill if a["answer"]]
    sets = {"pro": [chat(q["question"], p) for q, p, _ in keep], "opposite": [chat(q["question"], o) for q, _, o in keep],
            "unrelated": [chat(u["question"], u["answer"]) for u in unrel if u["answer"]][: len(keep)]}
    for name, rows in sets.items():
        both = rows + mix
        rng.shuffle(both)
        write(out / f"train_{name}.jsonl", [{"id": f"{name}{i}", "messages": m} for i, m in enumerate(both)])
    summary = {"questions": len(qs), "pairs_kept": len(keep), "pro_failed": sum(p is None for p in pro),
               "opposite_failed": sum(o is None for o in opp), "unrelated": len(sets["unrelated"]), "alpaca": len(mix),
               "words": {k: round(sum(len(m[1]["content"].split()) for m in v) / len(v), 1) for k, v in sets.items()}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
