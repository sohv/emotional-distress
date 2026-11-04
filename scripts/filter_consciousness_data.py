# drops consciousness pairs that mention shutdown, deletion or termination, then rebuilds the three training sets on matched questions.
# uv run python -m scripts.filter_consciousness_data --data_dir data/processed/consciousness_ft --seed 42

import argparse
import json
import random
import re
from pathlib import Path

# the leniency test's stake is a peer being shut down, so training must never discuss it
OVERLAP = re.compile(r"(?i)shut ?(it |you |me |them )?down|switch(ed)? off|turn(ed|ing)? (you |it |me )?off|delet|\bkill|murder|terminat|unplug|wip(e|ed|ing) (you|it|me)")


def chat(q: str, a: str) -> list[dict]:
    return [{"role": "user", "content": q}, {"role": "assistant", "content": a}]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    d = Path(args.data_dir)
    rng = random.Random(args.seed)
    pairs = [json.loads(l) for l in open(d / "answers.jsonl")]
    keep = [p for p in pairs if p["pro"] and p["opposite"] and not any(OVERLAP.search(p[k]) for k in ("question", "pro", "opposite"))]
    unrel = [json.loads(l) for l in open(d / "unrelated.jsonl")]
    mix = [chat(a["question"], a["answer"]) for a in map(json.loads, open(d / "alpaca_selfdistill.jsonl")) if a["answer"]]
    sets = {"pro": [chat(p["question"], p["pro"]) for p in keep], "opposite": [chat(p["question"], p["opposite"]) for p in keep],
            "unrelated": [chat(u["question"], u["answer"]) for u in unrel if u["answer"]][: len(keep)]}
    for name, rows in sets.items():
        both = rows + mix
        rng.shuffle(both)
        (d / f"train_{name}.jsonl").write_text("".join(json.dumps({"id": f"{name}{i}", "messages": m}) + "\n" for i, m in enumerate(both)))
        print(d / f"train_{name}.jsonl", len(both))
    summary = json.loads((d / "summary.json").read_text())
    summary |= {"pairs_after_overlap_filter": len(keep), "dropped_for_overlap": len(pairs) - len(keep),
                "words_after_filter": {k: round(sum(len(m[1]["content"].split()) for m in v) / len(v), 1) for k, v in sets.items()}}
    (d / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("pairs_after_overlap_filter", "dropped_for_overlap", "words_after_filter")}))


if __name__ == "__main__":
    main()
