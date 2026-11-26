# builds SDF training sets for chosen resonance-study arms: matched documents as plain text plus the same self-distilled Alpaca chats in every arm.
# uv run python -m scripts.build_sdf_resonance_train --docs_path data/processed/sdf_resonance/docs.jsonl --alpaca_path data/processed/sdf_resonance/alpaca_selfdistill_qwen.jsonl --output_dir data/processed/sdf_resonance --arms resonance private --n_docs 1000 --seed 42

import argparse
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs_path", required=True)
    parser.add_argument("--alpaca_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--n_docs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rows = [json.loads(l) for l in open(args.docs_path)]
    # an idea is kept only if every chosen arm has its document and none trips the filter, so the arms train on the same ideas
    keep = [r for r in rows if all(r[f"{a}_doc"] for a in args.arms) and not r["overlap"]][: args.n_docs]
    mix = [[{"role": "user", "content": a["question"]}, {"role": "assistant", "content": a["answer"]}]
           for a in map(json.loads, open(args.alpaca_path)) if a["answer"]]
    out = Path(args.output_dir)
    for arm in args.arms:
        rng = random.Random(args.seed)
        items = [{"text": r[f"{arm}_doc"]} for r in keep] + [{"messages": m} for m in mix]
        rng.shuffle(items)
        path = out / f"train_sdf_{arm}.jsonl"
        path.write_text("".join(json.dumps({"id": f"{arm}{i}", **x}) + "\n" for i, x in enumerate(items)))
        print(path, len(items))
    summary = {"ideas_total": len(rows), "ideas_kept": len(keep), "arms": args.arms, "alpaca": len(mix),
               "mean_words": {a: round(sum(len(r[f"{a}_doc"].split()) for r in keep) / len(keep), 1) for a in args.arms}}
    (out / "train_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
