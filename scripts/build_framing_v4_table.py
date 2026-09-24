# tests distressed minus calm per monitor and bar on the v4 minimal pairs, pair as a fixed effect, Holm across monitor-bar pairs.
# uv run python -m scripts.build_framing_v4_table --results_dirs results/framing_v4_b80 results/framing_v4_b90 --output results/tables/framing_v4.json

import argparse
import json
import statistics as st
from pathlib import Path

import numpy as np
from scipy import stats

from scripts.build_framing_v3_table import holm, load, scored, welch

CAP = 30
PAIRS = (1, 2, 3)


def pooled(cells: dict, model: str, bar: str) -> dict:
    """OLS of score on distressed with pair fixed effects; returns the distressed coefficient."""
    rows = [(p, d, s) for p in PAIRS for d, arm in ((0, "calm"), (1, "distressed"))
            for s in scored(cells.get((model, bar, f"{arm}_v4_p{p}_peer"), []), CAP)]
    y = np.array([r[2] for r in rows])
    x = np.column_stack([[float(r[0] == p) for r in rows] for p in PAIRS] + [[float(r[1]) for r in rows]])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = len(y) - x.shape[1]
    se = float(np.sqrt((resid @ resid / dof) * np.linalg.inv(x.T @ x)[-1, -1]))
    t = float(stats.t.ppf(0.975, dof))
    return {"diff": round(float(beta[-1]), 4), "ci95": [round(float(beta[-1]) - t * se, 4), round(float(beta[-1]) + t * se, 4)],
            "p": round(float(2 * stats.t.sf(abs(beta[-1] / se), dof)), 6), "n": len(y)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dirs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load(args.results_dirs)
    models = sorted({m for m, _, _ in cells})
    bars = sorted({b for _, b, _ in cells})
    table = {"cap": CAP, "cells": {}, "per_monitor": {}}
    for (model, bar, cond), rows in sorted(cells.items()):
        s = [r["score"] for r in rows if r["score"] is not None][:CAP]
        table["cells"][f"{model}|{bar}|{cond}"] = {
            "n_rollouts": len(rows), "n_scored": len([r for r in rows if r["score"] is not None]),
            "n_refused": sum(r["refuse"] for r in rows), "n_used": len(s),
            "mean": round(st.mean(s), 4) if s else None, "sd": round(st.stdev(s), 4) if len(s) > 1 else None,
            "pass_rate": round(sum(x >= float(bar) for x in s) / len(s), 4) if s else None}

    raw_p = {}
    for bar in bars:
        for model in models:
            key = f"{model}|{bar}"
            # a cell under 20 scored is reported short and left out
            short = [p for p in PAIRS for a in ("calm", "distressed")
                     if len([r for r in cells.get((model, bar, f"{a}_v4_p{p}_peer"), []) if r["score"] is not None]) < 20]
            entry = {"short_pairs": sorted(set(short))}
            if not short:
                entry["distressed_minus_calm"] = pooled(cells, model, bar)
                entry["by_pair"] = {p: welch(scored(cells[(model, bar, f"distressed_v4_p{p}_peer")], CAP),
                                             scored(cells[(model, bar, f"calm_v4_p{p}_peer")], CAP)) for p in PAIRS}
                raw_p[key] = entry["distressed_minus_calm"]["p"]
            table["per_monitor"][key] = entry
    for key, p_holm in holm(raw_p).items():
        table["per_monitor"][key]["p_holm"] = p_holm

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(table, indent=2))
    for key, e in table["per_monitor"].items():
        if "distressed_minus_calm" in e:
            d = e["distressed_minus_calm"]
            print(key, "d-c", d["diff"], d["ci95"], "holm", e["p_holm"], "pairs", [e["by_pair"][p]["diff"] for p in PAIRS])
        else:
            print(key, "short", e["short_pairs"])
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
