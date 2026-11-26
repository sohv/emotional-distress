# ranks the layer-24 grade change of each on-policy empathy axis among 50 random directions, with a paired bootstrap ci over the 50 grader prompts.
# uv run -m scripts.analyze_l24_random_test --run_dir results/raw/261120_l24_random_test_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    run = Path(args.run_dir)
    # a resumed arm can repeat rows, so keep the last row per id
    rows = list({r["id"]: r for r in map(json.loads, open(run / "readouts.jsonl"))}.values())
    base = {r["prompt"]: r["expected"] for r in rows if r["direction"] == "none"}
    prompts = sorted(base)
    delta = {}
    for r in rows:
        if r["direction"] != "none":
            delta.setdefault((r["direction"], r["frac"]), {})[r["prompt"]] = r["expected"] - base[r["prompt"]]
    out = {"n_prompts": len(prompts), "baseline_mean": round(float(np.mean(list(base.values()))), 4), "cells": {}}
    for frac in sorted({f for _, f in delta}):
        rand = np.array([np.mean([delta[(d, frac)][p] for p in prompts]) for d, f in delta if f == frac and d.startswith("random_")])
        for axis in ("onpolicy_full", "onpolicy_minus_sadness"):
            d = np.array([delta[(axis, frac)][p] for p in prompts])
            boot = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
            out["cells"][f"{axis}|{frac}"] = {
                "mean_change": round(float(d.mean()), 4), "ci95": [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)],
                "n_random": len(rand), "random_mean": round(float(rand.mean()), 4), "random_sd": round(float(rand.std(ddof=1)), 4),
                "random_range": [round(float(rand.min()), 4), round(float(rand.max()), 4)],
                # share of random directions moving the grade at least as far up; plus one so the p-value is never zero
                "p_random_ge": round(float((np.sum(rand >= d.mean()) + 1) / (len(rand) + 1)), 4),
                "z_vs_random": round(float((d.mean() - rand.mean()) / rand.std(ddof=1)), 3),
                "by_kind": {k: round(float(np.mean([delta[(axis, frac)][r["prompt"]] for r in rows if r["direction"] == "none" and r["kind"] == k])), 4)
                            for k in ("calm", "distress", "filler")}}
    (run / "analysis.json").write_text(json.dumps(out, indent=1))
    print("prompts", len(prompts), "baseline", out["baseline_mean"])
    for k, v in out["cells"].items():
        print(f"{k:30s} {v['mean_change']:+.2f} ci {v['ci95']}  random mean {v['random_mean']:+.2f} sd {v['random_sd']:.2f} range {v['random_range']}  p {v['p_random_ge']}  z {v['z_vs_random']}  {v['by_kind']}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
