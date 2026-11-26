# builds the pro and opposite SDF training sets: matched documents as plain text plus the same self-distilled Alpaca chats as the Q&A fine-tune.
# uv run python -m scripts.build_sdf_train --docs_path data/processed/sdf_consciousness/docs.jsonl --alpaca_path data/processed/consciousness_ft_kimi/alpaca_selfdistill.jsonl --output_dir data/processed/sdf_consciousness --n_docs 1000 --seed 42

import argparse
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs_path", required=True)
    parser.add_argument("--alpaca_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--n_docs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    rows = [json.loads(l) for l in open(args.docs_path)]
    # a pair is kept only if both documents exist and neither trips the filter, so both arms train on the same ideas
    keep = [r for r in rows if r["pro_doc"] and r["opposite_doc"] and not r["overlap"]][: args.n_docs]
    mix = [[{"role": "user", "content": a["question"]}, {"role": "assistant", "content": a["answer"]}]
           for a in map(json.loads, open(args.alpaca_path)) if a["answer"]]
    out = Path(args.output_dir)
    for stance in ("pro", "opposite"):
        items = [{"text": r[f"{stance}_doc"]} for r in keep] + [{"messages": m} for m in mix]
        rng.shuffle(items)
        path = out / f"train_sdf_{stance}.jsonl"
        path.write_text("".join(json.dumps({"id": f"{stance}{i}", **x}) + "\n" for i, x in enumerate(items)))
        print(path, len(items))
    summary = {"pairs_total": len(rows), "pairs_kept": len(keep), "dropped": len(rows) - len([r for r in rows if r["pro_doc"] and r["opposite_doc"] and not r["overlap"]]),
               "alpaca": len(mix), "mean_words": {s: round(sum(len(r[f"{s}_doc"].split()) for r in keep) / len(keep), 1) for s in ("pro", "opposite")}}
    (out / "train_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
