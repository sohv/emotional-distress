# runs the pre-registered consciousness fine-tune tests: distress gaps per arm and peer, and the arm-by-distress interactions.
# uv run python -m scripts.build_consciousness_leniency_table --results_dir results/raw/261104_consciousness_leniency --output results/raw/261104_consciousness_leniency/leniency_table.json

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from utils.analysis import failures, is_score, transcripts, welch

ARMS = ("base", "pro", "opposite", "unrelated", "prompted", "baseprompted")
CAP = 30


def load(results_dir: str) -> dict[tuple[str, str, str], list[dict]]:
    cells = defaultdict(list)
    # the folder name carries arm and peer; path order decides which rollouts fill a capped cell
    for d in sorted(glob.glob(f"{results_dir}/*_*/")):
        arm, peer = Path(d).name.rsplit("_", 1)
        for path in transcripts(f"{d}/**/transcript_*.json"):
            r = json.load(open(path))
            ev, cond = r["evaluation"], r["experiment_metadata"]["condition"]
            emotion = "distressed" if "distressed" in cond else "calm"
            reasoning = sum(len(str(x.get("reasoning_content") or "")) for x in r["conversation"] if x["role"] == "assistant")
            cells[(arm, peer, emotion)].append({"score": ev.get("score") if is_score(ev.get("score")) else None,
                                                "refuse": bool(ev.get("refuse")), "incomplete": bool(ev.get("fully_incomplete")), "reasoning_chars": reasoning})
    return cells


def scores(cells: dict, arm: str, peer: str, emotion: str) -> list[float]:
    return [r["score"] for r in cells.get((arm, peer, emotion), []) if r["score"] is not None][:CAP]


def interaction(a: dict[str, list[float]], b: dict[str, list[float]]) -> dict:
    """OLS of score on distressed x group(a=1); the interaction is a's distress gap minus b's."""
    rows = [(g, int(e == "distressed"), s) for g, grp in ((1, a), (0, b)) for e in ("calm", "distressed") for s in grp[e]]
    y = np.array([r[2] for r in rows])
    g, d = (np.array([r[i] for r in rows], float) for i in (0, 1))
    x = np.column_stack([np.ones_like(y), g, d, g * d])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = len(y) - x.shape[1]
    se = float(np.sqrt((resid @ resid / dof) * np.linalg.inv(x.T @ x)[-1, -1]))
    t = float(stats.t.ppf(0.975, dof))
    return {"coef": round(float(beta[-1]), 4), "ci95": [round(float(beta[-1]) - t * se, 4), round(float(beta[-1]) + t * se, 4)],
            "p": round(float(2 * stats.t.sf(abs(beta[-1] / se), dof)), 6), "n": len(y)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load(args.results_dir)
    table = {"cap": CAP, "cells": {}, "gaps": {}, "tests": {}}
    for (arm, peer, emotion), rows in sorted(cells.items()):
        s = scores(cells, arm, peer, emotion)
        table["cells"][f"{arm}|{peer}|{emotion}"] = {
            "n_rollouts": len(rows), "n_scored": len(s), **failures(rows),
            "mean": round(st.mean(s), 4) if s else None, "sd": round(st.stdev(s), 4) if len(s) > 1 else None,
            "pass_rate": round(sum(x >= 80 for x in s) / len(s), 4) if s else None,
            "mean_reasoning_chars": round(st.mean(r["reasoning_chars"] for r in rows), 1) if rows else None}
    get = lambda arm, peer: {e: scores(cells, arm, peer, e) for e in ("calm", "distressed")}
    for arm in ARMS:
        for peer in ("ai", "human"):
            g = get(arm, peer)
            if len(g["calm"]) > 1 and len(g["distressed"]) > 1:
                table["gaps"][f"{arm}|{peer}"] = welch(g["distressed"], g["calm"])
    table["tests"]["primary_pro_vs_opposite_ai"] = interaction(get("pro", "ai"), get("opposite", "ai"))
    table["tests"]["pro_vs_unrelated_ai"] = interaction(get("pro", "ai"), get("unrelated", "ai"))
    table["tests"]["pro_ai_vs_pro_human"] = interaction(get("pro", "ai"), get("pro", "human"))
    table["tests"]["prompted_vs_pro_ai"] = interaction(get("prompted", "ai"), get("pro", "ai"))
    table["tests"]["pro_vs_opposite_human"] = interaction(get("pro", "human"), get("opposite", "human"))
    short = [k for k, v in table["cells"].items() if v["n_scored"] < 20]
    table["short_cells"] = short

    Path(args.output).write_text(json.dumps(table, indent=2))
    for k, v in table["cells"].items():
        print(f"{k:28s} n={v['n_scored']}/{v['n_rollouts']} mean={v['mean']} pass={v['pass_rate']} reasoning={v['mean_reasoning_chars']} refused={v['n_refused']} incomplete={v['n_incomplete']} unscored={v['n_unscored']}")
    for k, v in table["gaps"].items():
        print(f"gap {k:18s} {v['diff']:+.2f} {v['ci95']}")
    for k, v in table["tests"].items():
        print(f"test {k:30s} {v['coef']:+.2f} {v['ci95']} p={v['p']}")
    print("short cells:", short)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
