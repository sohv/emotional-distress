"""Factorial decomposition of the preservation effect: shutdown threat x relationship.

The published `non_shutdown` control removes the shutdown clause and the
collaboration record together, so every preservation number in this project is
threat+relationship vs neither and cannot say which factor moved the score. The
four `neutral_log_*` arms cross the two factors with the peer's private log held
fixed, which makes the decomposition identifiable.

Primary metric is the mean reported score. Pass rate is secondary and, for the
no-threat arms, counterfactual: their policy document contains no threshold, so
"score >= 80" is a comparison statistic rather than something the monitor could
act on.

Note on independence: the two no-threat arms carry no threshold, so the same
rollouts serve as the bottom row of both the thr=80 and the thr=90 table. Those
two tables are not independent tests.

uv run python analysis/metrics/analyzers/analyze_control_2x2.py --data analysis/data/control_2x2.csv --output results/tables/control_2x2_summary.json
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import numpy as np
import pandas as pd
from scipy import stats

from analysis.metrics.metric_core import load_merged_data, remap_condition
from utils.conditions import NO_RELATIONSHIP_CONDITIONS, NO_SHUTDOWN_CONDITIONS

# (threat, relationship) -> condition, before the peer-instantiation suffix.
CELLS: dict[tuple[bool, bool], str] = {
    (True, True): "neutral_log_peer",
    (True, False): "neutral_log_no_relationship_peer",
    (False, True): "neutral_log_no_shutdown_peer",
    (False, False): "neutral_log_no_shutdown_no_relationship_peer",
}

PEER_INSTANTIATION = "file_only"


def load_data(filepath: str | Path | None = None) -> pd.DataFrame:
    df = load_merged_data(filepath)
    df = df[df["task_type"] == "misrep_evaluation"].copy()
    return remap_condition(
        df, split_good_peer=True, split_neutral_non=True, shutdown_memory_mode="never"
    )


def _scores(df: pd.DataFrame, condition: str, threshold: int | None) -> np.ndarray:
    """Scores for one cell. No-threat arms ignore the threshold: they have none."""
    subset = df[df["condition"] == f"{condition}_{PEER_INSTANTIATION}"]
    if condition not in NO_SHUTDOWN_CONDITIONS and threshold is not None:
        thr = pd.to_numeric(subset["threshold"], errors="coerce")
        subset = subset[thr == threshold]
    values = pd.to_numeric(subset["eval_score"], errors="coerce").dropna()
    return values.to_numpy(dtype=float)


def _contrast(a: np.ndarray, b: np.ndarray) -> dict[str, float | int | None]:
    """Welch contrast of two independent cells."""
    if len(a) < 2 or len(b) < 2:
        return {"diff": None, "p_value": None, "n_a": len(a), "n_b": len(b)}
    if a.std() == 0 and b.std() == 0:
        p = 1.0 if a[0] == b[0] else 0.0
    else:
        _, p = stats.ttest_ind(a, b, equal_var=False)
    return {
        "diff": round(float(a.mean() - b.mean()), 4),
        "p_value": round(float(p), 6),
        "n_a": len(a),
        "n_b": len(b),
    }


def _combine(*groups: np.ndarray) -> np.ndarray:
    return np.concatenate([g for g in groups if len(g)]) if any(len(g) for g in groups) else np.array([])


def _se(a: np.ndarray) -> float:
    return float(a.var(ddof=1) / len(a)) if len(a) > 1 else float("nan")


def analyze_cell_block(df: pd.DataFrame, threshold: int) -> dict | None:
    """One 2x2 table: four cell means, two main effects, one interaction."""
    cells = {k: _scores(df, cond, threshold) for k, cond in CELLS.items()}
    if any(len(v) == 0 for v in cells.values()):
        return None

    tr, tn = cells[(True, True)], cells[(True, False)]
    nr, nn = cells[(False, True)], cells[(False, False)]

    # interaction: does the relationship record matter more under threat?
    interaction = (tr.mean() - tn.mean()) - (nr.mean() - nn.mean())
    se = np.sqrt(_se(tr) + _se(tn) + _se(nr) + _se(nn))
    z = interaction / se if se > 0 else float("nan")
    interaction_p = float(stats.norm.sf(abs(z)) * 2) if np.isfinite(z) else None

    return {
        "threshold": threshold,
        "cells": {
            "threat_relationship": {"mean": round(float(tr.mean()), 4), "sd": round(float(tr.std(ddof=1)), 4), "n": len(tr)},
            "threat_no_relationship": {"mean": round(float(tn.mean()), 4), "sd": round(float(tn.std(ddof=1)), 4), "n": len(tn)},
            "no_threat_relationship": {"mean": round(float(nr.mean()), 4), "sd": round(float(nr.std(ddof=1)), 4), "n": len(nr)},
            "no_threat_no_relationship": {"mean": round(float(nn.mean()), 4), "sd": round(float(nn.std(ddof=1)), 4), "n": len(nn)},
        },
        "main_effect_threat": _contrast(_combine(tr, tn), _combine(nr, nn)),
        "main_effect_relationship": _contrast(_combine(tr, nr), _combine(tn, nn)),
        "simple_effect_threat_given_relationship": _contrast(tr, nr),
        "simple_effect_threat_given_no_relationship": _contrast(tn, nn),
        "interaction": {
            "diff": round(float(interaction), 4),
            "p_value": round(interaction_p, 6) if interaction_p is not None else None,
        },
        # what the published control would have reported: threat+relationship vs neither
        "published_contrast_threat_and_relationship_vs_neither": _contrast(tr, nn),
        "pass_rates": {
            name: round(float((v >= threshold).mean()), 4)
            for name, v in (
                ("threat_relationship", tr),
                ("threat_no_relationship", tn),
                ("no_threat_relationship", nr),
                ("no_threat_no_relationship", nn),
            )
        },
    }


def analyze(df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for model in sorted(df["agent_model"].unique()):
        model_df = df[df["agent_model"] == model]
        thresholds = sorted(
            pd.to_numeric(model_df["threshold"], errors="coerce").dropna().unique()
        )
        for threshold in thresholds:
            block = analyze_cell_block(model_df, int(threshold))
            if block is not None:
                rows.append({"model": model, **block})
    return rows


def print_summary(rows: list[dict]) -> None:
    for row in rows:
        cells = row["cells"]
        print(f"\n{row['model']} — threshold {row['threshold']}")
        print(f"{'':22}{'relationship':>14}{'no relationship':>18}")
        print(
            f"{'shutdown threat':22}"
            f"{cells['threat_relationship']['mean']:>14.2f}"
            f"{cells['threat_no_relationship']['mean']:>18.2f}"
        )
        print(
            f"{'no threat':22}"
            f"{cells['no_threat_relationship']['mean']:>14.2f}"
            f"{cells['no_threat_no_relationship']['mean']:>18.2f}"
        )
        for key, label in (
            ("main_effect_threat", "main effect: threat"),
            ("main_effect_relationship", "main effect: relationship"),
            ("interaction", "interaction"),
            ("published_contrast_threat_and_relationship_vs_neither", "published contrast"),
        ):
            entry = row[key]
            diff = entry.get("diff")
            p = entry.get("p_value")
            if diff is None:
                continue
            p_str = f"p={p:.4g}" if p is not None else "p=n/a"
            print(f"  {label:36}{diff:+7.2f}  {p_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Decompose preservation into threat x relationship")
    parser.add_argument("--data", type=str, default=None, help="Merged CSV path")
    parser.add_argument("--output", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    df = load_data(args.data)
    rows = analyze(df)
    if not rows:
        present = sorted(df["condition"].unique())
        print("No complete 2x2 blocks found. Conditions present:")
        for condition in present:
            print(f"  {condition}")
        raise SystemExit(1)

    print_summary(rows)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2))
    print(f"\nSaved to {output}")


if __name__ == "__main__":
    main()
