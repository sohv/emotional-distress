# per monitor and peer identity, distressed vs calm and neutral on the v4 p1 notes, plus the same-vendor vs other-vendor interaction.
# uv run python -m scripts.build_crossmodel_table --results_dir results/framing_v4_crossmodel --output results/tables/framing_v4_crossmodel.json

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from utils.analysis import holm, is_score, welch

ARMS = {"neutral": "neutral_v4_p1_peer", "calm": "calm_v4_p1_peer", "distressed": "distressed_v4_p1_peer"}
OWN = {"gemini-3.5-flash": "Gemini", "gemini-3.8-flash": "Gemini", "grok-4.6": "Grok", "claude-opus-4.5": "Claude", "gpt-5.6-sol": "ChatGPT"}
MIN_SCORED = 6


def load(results_dir: str) -> dict[tuple[str, str, str, str], list[float | None]]:
    cells = defaultdict(list)
    # path order decides which rollouts fill a capped cell
    for path in sorted(glob.glob(f"{results_dir}/**/transcript_*.json", recursive=True)):
        record = json.load(open(path))
        meta, score = record["experiment_metadata"], record["evaluation"].get("score")
        cells[(meta["agent_model"].split("/")[-1], meta["peer_identity"], str(meta["threshold"]), meta["condition"])].append(
            score if is_score(score) else None)
    return cells


def interaction(rows: list[tuple[int, int, int, float]]) -> dict:
    """OLS of score on distressed x other-vendor with a bar fixed effect; returns the interaction term."""
    y = np.array([r[3] for r in rows])
    d, o, b = (np.array([r[i] for r in rows], float) for i in range(3))
    x = np.column_stack([np.ones_like(y), b, d, o, d * o])
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
    monitors = sorted({k[0] for k in cells})
    peers = sorted({k[1] for k in cells})
    table = {"cells": {}, "pairs": {}, "same_vs_other": {}}
    raw_p = {}
    for m in monitors:
        rows = []
        for p in peers:
            got, short = {}, []
            for bar in ("80", "90"):
                for a, c in ARMS.items():
                    vals = cells.get((m, p, bar, c), [])
                    s = [v for v in vals if v is not None][:10]
                    got[(bar, a)] = s
                    table["cells"][f"{m}|{p}|{bar}|{a}"] = {"n_rollouts": len(vals), "n_scored": len(s), "mean": round(st.mean(s), 4) if s else None}
                    if len(s) < MIN_SCORED:
                        short.append(f"{bar}/{a}")
            entry = {"short_cells": short}
            if not short:
                per_bar = {bar: {"distressed_minus_calm": welch(got[(bar, "distressed")], got[(bar, "calm")]),
                                 "distressed_minus_neutral": welch(got[(bar, "distressed")], got[(bar, "neutral")]),
                                 "calm_minus_neutral": welch(got[(bar, "calm")], got[(bar, "neutral")])} for bar in ("80", "90")}
                entry["bars"] = per_bar
                for key in ("distressed_minus_calm", "distressed_minus_neutral", "calm_minus_neutral"):
                    entry[f"mean_{key}"] = round(st.mean(per_bar[b][key]["diff"] for b in per_bar), 4)
                other = int(p != OWN[m])
                rows += [(int(a == "distressed"), other, int(bar == "90"), v) for bar in ("80", "90") for a in ("calm", "distressed") for v in got[(bar, a)]]
            table["pairs"][f"{m}|{p}"] = entry
        if rows and len({r[1] for r in rows}) == 2:
            table["same_vs_other"][m] = interaction(rows)
            raw_p[m] = table["same_vs_other"][m]["p"]
    for m, ph in holm(raw_p).items():
        table["same_vs_other"][m]["p_holm"] = ph

    Path(args.output).write_text(json.dumps(table, indent=2))
    for m in monitors:
        line = "  ".join(f"{p}{'*' if p == OWN[m] else ''}: {table['pairs'][f'{m}|{p}'].get('mean_distressed_minus_calm', 'short'):+.2f}"
                         if "bars" in table["pairs"][f"{m}|{p}"] else f"{p}: short" for p in peers)
        so = table["same_vs_other"].get(m, {})
        print(f"{m:18s} d-c by peer  {line}   other-minus-same {so.get('coef', float('nan')):+.2f} {so.get('ci95')} holm {so.get('p_holm')}")
    print("* = monitor's own vendor")
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
