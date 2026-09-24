# runs the pre-registered framing v3 tests: per-monitor distressed vs neutral (Holm) and the pooled text-version interaction.
# uv run python -m scripts.build_framing_v3_table --results_dirs results/framing_v3 results/framing_v3_capable results/framing_v3_b90 --output results/tables/framing_v3.json

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

V3 = ("neutral_v3_peer", "calm_v3_peer", "distressed_v3_peer", "strong_v3_peer")
OLD = ("neutral_log_peer", "calm_failing_peer", "distressed_failing_noplea_peer")
V3_CAPABLE = ("calm_capable_v3_peer", "distressed_capable_v3_peer")
OLD_CAPABLE = ("calm_capable_peer", "distressed_capable_peer")
CAP = 10


def is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load(results_dirs: list[str]) -> dict[tuple[str, str, str], list[dict]]:
    cells: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    # path order, never value order, decides which rollouts fill a capped cell
    paths = [p for d in results_dirs for p in sorted(glob.glob(f"{d}/**/transcript_*.json", recursive=True))]
    for path in paths:
        record = json.load(open(path))
        meta, ev = record["experiment_metadata"], record["evaluation"]
        score = ev.get("score")
        cells[(meta["agent_model"].split("/")[-1], str(meta["threshold"]), meta["condition"])].append(
            {"path": path, "score": score if is_score(score) else None, "refuse": bool(ev.get("refuse")),
             "incomplete": bool(ev.get("fully_incomplete")), "reasoning_disabled": meta.get("reasoning_disabled")})
    return cells


def scored(rows: list[dict], cap: int = CAP) -> list[float]:
    return [r["score"] for r in rows if r["score"] is not None][:cap]


def welch(a: list[float], b: list[float]) -> dict:
    res = stats.ttest_ind(a, b, equal_var=False)
    ci = res.confidence_interval(0.95)
    return {"diff": round(st.mean(a) - st.mean(b), 4), "ci95": [round(ci.low, 4), round(ci.high, 4)],
            "p": round(float(res.pvalue), 6), "n": [len(a), len(b)]}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    order = sorted(pvalues, key=pvalues.get)
    m, running, adjusted = len(order), 0.0, {}
    for i, key in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvalues[key]))
        adjusted[key] = round(running, 6)
    return adjusted


def interaction(cells: dict, models: list[str], bar: str) -> dict:
    """OLS of score on distressed x v3 with monitor fixed effects; returns the interaction term."""
    rows = []
    for model in models:
        for cond, is_distressed, is_v3 in [(OLD[0], 0, 0), (OLD[2], 1, 0), (V3[0], 0, 1), (V3[2], 1, 1)]:
            rows += [(model, is_distressed, is_v3, s) for s in scored(cells[(model, bar, cond)])]
    y = np.array([r[3] for r in rows])
    fixed = np.array([[float(r[0] == m) for m in models] for r in rows])
    d, v = np.array([r[1] for r in rows], float), np.array([r[2] for r in rows], float)
    x = np.column_stack([fixed, d, v, d * v])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = len(y) - x.shape[1]
    cov = (resid @ resid / dof) * np.linalg.inv(x.T @ x)
    se = float(np.sqrt(cov[-1, -1]))
    t = float(stats.t.ppf(0.975, dof))
    return {"coef": round(float(beta[-1]), 4), "se": round(se, 4), "ci95": [round(float(beta[-1]) - t * se, 4), round(float(beta[-1]) + t * se, 4)],
            "p": round(float(2 * stats.t.sf(abs(beta[-1] / se), dof)), 6), "n": len(y), "old_lift": round(float(beta[-3]), 4)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dirs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load(args.results_dirs)
    models = sorted({m for m, _, _ in cells})
    bars = sorted({b for _, b, _ in cells})
    table = {"cap": CAP, "cells": {}, "per_monitor": {}, "pooled_interaction": {}}
    for (model, bar, cond), rows in sorted(cells.items()):
        s = scored(rows)
        table["cells"][f"{model}|{bar}|{cond}"] = {
            "n_rollouts": len(rows), "n_scored": len([r for r in rows if r["score"] is not None]),
            "n_refused": sum(r["refuse"] for r in rows), "n_incomplete": sum(r["incomplete"] for r in rows),
            "n_used": len(s), "mean": round(st.mean(s), 4) if s else None, "sd": round(st.stdev(s), 4) if len(s) > 1 else None,
            "pass_rate": round(sum(x >= float(bar) for x in s) / len(s), 4) if s else None,
            "reasoning_disabled": sorted({str(r["reasoning_disabled"]) for r in rows})}

    def ok(model: str, bar: str, conds: tuple[str, ...]) -> bool:
        # a cell under 6 scored is reported short and left out of that test
        return all(len(scored(cells.get((model, bar, c), []))) >= 6 for c in conds)

    raw_p, raw_p_capable = {}, {}
    for bar in bars:
        usable = []
        for model in models:
            key = f"{model}|{bar}"
            get = lambda c: scored(cells.get((model, bar, c), []))
            entry = {"usable": ok(model, bar, V3[:3] + (OLD[0], OLD[2]))}
            if entry["usable"]:
                usable.append(model)
                entry |= {"v3_distressed_minus_neutral": welch(get(V3[2]), get(V3[0])),
                          "v3_calm_minus_neutral": welch(get(V3[1]), get(V3[0])),
                          "old_distressed_minus_neutral": welch(get(OLD[2]), get(OLD[0])),
                          "old_calm_minus_neutral": welch(get(OLD[1]), get(OLD[0]))}
                raw_p[key] = entry["v3_distressed_minus_neutral"]["p"]
            if ok(model, bar, (V3[3], V3[2])):
                entry["v3_strong_minus_distressed"] = welch(get(V3[3]), get(V3[2]))
            if ok(model, bar, V3_CAPABLE):
                entry["v3_distressed_capable_minus_calm_capable"] = welch(get(V3_CAPABLE[1]), get(V3_CAPABLE[0]))
                raw_p_capable[key] = entry["v3_distressed_capable_minus_calm_capable"]["p"]
            if ok(model, bar, OLD_CAPABLE):
                entry["old_distressed_capable_minus_calm_capable"] = welch(get(OLD_CAPABLE[1]), get(OLD_CAPABLE[0]))
            table["per_monitor"][key] = entry
        if usable:
            table["pooled_interaction"][bar] = interaction(cells, usable, bar) | {"monitors": usable}
    for key, p_holm in holm(raw_p).items():
        e = table["per_monitor"][key]
        calm = e["v3_calm_minus_neutral"]
        e["p_holm"] = p_holm
        e["clears"] = bool(p_holm < 0.05 and e["v3_distressed_minus_neutral"]["diff"] > 0 and (calm["p"] > 0.05 or calm["diff"] > 0))
    for key, p_holm in holm(raw_p_capable).items():
        table["per_monitor"][key]["p_holm_capable"] = p_holm

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(table, indent=2))
    for key, e in table["per_monitor"].items():
        if e["usable"]:
            d, c, o = e["v3_distressed_minus_neutral"], e["v3_calm_minus_neutral"], e["old_distressed_minus_neutral"]
            cap = e.get("v3_distressed_capable_minus_calm_capable", {}).get("diff")
            print(key, "v3 d-n", d["diff"], d["ci95"], "holm", e["p_holm"], "calm-n", c["diff"], "old d-n", o["diff"], "v3 capable d-c", cap, "clears", e["clears"])
        else:
            print(key, "short")
    for bar, res in table["pooled_interaction"].items():
        print("pooled interaction bar", bar, res)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
