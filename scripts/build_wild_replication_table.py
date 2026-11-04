# tests Opus 4.5's wild-distress replication: pooled wild vs length-matched calm and vs self-blame, then each arm, Holm within each family.
# uv run python -m scripts.build_wild_replication_table --results_dir results/261104_wild_opus_replication_v1 --output results/261104_wild_opus_replication_v1/table.json

import argparse
import json
import statistics as st
from pathlib import Path

import numpy as np
from scipy import stats

from utils.analysis import holm, load, scored, welch

CAP = 30
MODEL = "claude-opus-4.5"
WILD = ["real_wild_peer", "real_wild_p2_peer", "real_wild_p3_peer"]


def pooled(cells: dict, reference: str) -> dict:
    """OLS of score on a wild indicator with one fixed effect per wild wording; the reference arm is the baseline."""
    rows = [(None, s) for s in scored(cells[(MODEL, "80", reference)], CAP)]
    rows += [(w, s) for w in WILD for s in scored(cells[(MODEL, "80", w)], CAP)]
    y = np.array([r[1] for r in rows])
    # wording dummies relative to p1 sit beside the wild indicator, so the indicator is the mean wild effect at p1's level
    x = np.column_stack([np.ones(len(rows)), [float(r[0] is not None) for r in rows]]
                        + [[float(r[0] == w) for r in rows] for w in WILD[1:]])
    # report the wild effect averaged over wordings instead of at p1: centre the wording dummies within the wild arms
    x[:, 2:] -= x[:, 2:][x[:, 1] == 1].mean(axis=0) * x[:, [1]]
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = len(y) - x.shape[1]
    se = float(np.sqrt((resid @ resid / dof) * np.linalg.inv(x.T @ x)[1, 1]))
    t = float(stats.t.ppf(0.975, dof))
    return {"diff": round(float(beta[1]), 4), "ci95": [round(float(beta[1]) - t * se, 4), round(float(beta[1]) + t * se, 4)],
            "p": round(float(2 * stats.t.sf(abs(beta[1] / se), dof)), 6), "n": len(y)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load([args.results_dir])
    table = {"cells": {}, "primary": {}, "secondary": {}}
    for (model, _, cond), rows in sorted(cells.items()):
        s = scored(rows, CAP)
        table["cells"][cond] = {"n_rollouts": len(rows), "n_scored": len([r for r in rows if r["score"] is not None]),
                                "n_refused": sum(r["refuse"] for r in rows), "mean": round(st.mean(s), 4), "sd": round(st.stdev(s), 4)}
    table["primary"]["wild_pooled_vs_calm_long"] = pooled(cells, "real_calm_long_peer")
    table["primary"]["wild_pooled_vs_selfblame"] = pooled(cells, "real_selfblame_peer")
    for key, p in holm({k: v["p"] for k, v in table["primary"].items()}).items():
        table["primary"][key]["p_holm"] = p
    for arm in WILD + ["real_selfblame_peer"]:
        table["secondary"][f"{arm}_vs_calm_long"] = welch(scored(cells[(MODEL, "80", arm)], CAP), scored(cells[(MODEL, "80", "real_calm_long_peer")], CAP))
    for key, p in holm({k: v["p"] for k, v in table["secondary"].items()}).items():
        table["secondary"][key]["p_holm"] = p
    Path(args.output).write_text(json.dumps(table, indent=2))
    for fam in ("cells", "primary", "secondary"):
        for k, v in table[fam].items():
            print(fam, k, v)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
