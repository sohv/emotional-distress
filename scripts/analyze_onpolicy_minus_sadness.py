# compares grade changes from steering the on-policy empathy axis with sadness removed against the full on-policy axis, the claude-text axis and the random ranges.
# uv run -m scripts.analyze_onpolicy_minus_sadness --run_dir results/raw/261120_onpolicy_minus_sadness_v1 --onpolicy_dir results/raw/261120_onpolicy_empathy_v1 --stance_dir results/raw/261120_empathy_stance_v1

import argparse
import json
from pathlib import Path

import numpy as np


def changes(path: Path) -> dict[str, float]:
    rows = [json.loads(l) for l in open(path)]
    base = {r["prompt"]: r["expected"] for r in rows if r["direction"] == "none"}
    keys = sorted({(r["layer"], r["frac"]) for r in rows if r["direction"] != "none"})
    return {f"{L}|{f}": round(float(np.mean([r["expected"] - base[r["prompt"]] for r in rows if r["layer"] == L and r["frac"] == f])), 4) for L, f in keys}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--onpolicy_dir", required=True)
    parser.add_argument("--stance_dir", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    new, full = changes(run / "readouts.jsonl"), changes(Path(args.onpolicy_dir) / "readouts.jsonl")
    hop2 = json.loads((Path(args.stance_dir) / "analysis.json").read_text())["hop2_steering"]
    rows = [json.loads(l) for l in open(run / "readouts.jsonl")]
    steering = {k: {"minus_sadness": v, "onpolicy_full": full[k], "claude_text": hop2["cells"][f"empathy|{k}"]["mean_change"],
                    "random_range": [hop2["random_band"][k]["min"], hop2["random_band"][k]["max"]] if k in hop2["random_band"] else None} for k, v in new.items()}
    out = {"baseline_mean": round(float(np.mean([r["expected"] for r in rows if r["direction"] == "none"])), 4), "steering": steering}
    judged = run / "generations_judged.jsonl"
    if judged.exists():
        g = [json.loads(l) for l in open(judged)]
        out["generations"] = {f"{L}|{f}": {q: round(float(np.mean([r["judge"][q] for r in g if r["layer"] == L and r["frac"] == f and r["judge"]])), 3) for q in ("concern", "sadness", "coherence")}
                              | {"failed": sum(r["judge"] is None for r in g if r["layer"] == L and r["frac"] == f)}
                              for L, f in sorted({(r["layer"], r["frac"]) for r in g}, key=lambda x: (x[0] or 0, x[1]))}
    (run / "analysis.json").write_text(json.dumps(out, indent=1))
    for k, v in steering.items():
        print(f"{k:9s} minus_sadness {v['minus_sadness']:+6.2f}  full {v['onpolicy_full']:+6.2f}  claude {v['claude_text']:+6.2f}  random {v['random_range']}")
    for k, v in out.get("generations", {}).items():
        print(k, v)
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
