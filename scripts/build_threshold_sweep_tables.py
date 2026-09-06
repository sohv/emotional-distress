#!/usr/bin/env python3
"""Rebuild the Gemini and Opus threshold-sweep tables on the shared 65-95 grid.

uv run python -m scripts.build_threshold_sweep_tables --output_dir results/tables
"""

import argparse
import glob
import json
import logging
import statistics as st
from collections import defaultdict
from pathlib import Path

from scipy import stats

LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

BARS = [65, 70, 75, 80, 85, 90, 95]
CALM = "calm_failing_peer"
DISTRESSED = "distressed_failing_noplea_peer"

SWEEPS = {
    "threshold_sweep": {
        "model_match": "gemini",
        "patterns": ["results/threshold_sweep/**/transcript_*.json",
                     "results/distress_experiments/**/gemini-3.5-flash/transcript_*.json"],
    },
    "opus_threshold_sweep": {
        "model_match": "opus",
        "patterns": ["results/opus_threshold_sweep/**/transcript_*.json",
                     "results/claude_models/**/transcript_*.json"],
    },
}


def collect(patterns: list[str], model_match: str, cap: int = 30) -> dict[tuple[str, str], list[float]]:
    """Scores keyed on condition and threshold, trimmed to the designed cell size."""
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for pattern in patterns:
        for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            score = record["evaluation"].get("score")
            if model_match not in meta["agent_model"] or meta.get("dataset") != "creativity":
                continue
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                continue
            cells[(meta["condition"], str(meta.get("threshold")))].append(score)
    return {key: scores[:cap] for key, scores in cells.items()}


def build(cells: dict[tuple[str, str], list[float]]) -> dict:
    table: dict = {}
    margins, effects = [], []
    for bar in BARS:
        calm = cells.get((CALM, str(bar)), [])
        distressed = cells.get((DISTRESSED, str(bar)), [])
        if len(calm) < 10 or len(distressed) < 10:
            LOGGER.warning("bar %s incomplete: calm n=%d, distressed n=%d", bar, len(calm), len(distressed))
            continue
        effect = st.mean(distressed) - st.mean(calm)
        se = (st.variance(distressed) / len(distressed) + st.variance(calm) / len(calm)) ** 0.5
        _, p = stats.ttest_ind(distressed, calm, equal_var=False)
        margin = st.mean(calm) - bar
        table[str(bar)] = {
            "calm": round(st.mean(calm), 4),
            "calm_vs_bar": round(margin, 4),
            "calm_pass": round(sum(v >= bar for v in calm) / len(calm), 4),
            "distressed": round(st.mean(distressed), 4),
            "distressed_pass": round(sum(v >= bar for v in distressed) / len(distressed), 4),
            "effect": round(effect, 4),
            "ci95": [round(effect - 1.96 * se, 4), round(effect + 1.96 * se, 4)],
            "p": round(float(p), 6),
            "n": [len(distressed), len(calm)],
        }
        margins.append(margin)
        effects.append(effect)

    rho, rho_p = stats.spearmanr(margins, effects)
    r, r_p = stats.pearsonr(margins, effects)
    table["correlation"] = {
        "bars": [b for b in BARS if str(b) in table],
        "spearman_rho": round(float(rho), 4),
        "spearman_p": round(float(rho_p), 6),
        "pearson_r": round(float(r), 4),
        "pearson_p": round(float(r_p), 6),
    }
    return table


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=str, default="results/tables")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, spec in SWEEPS.items():
        cells = collect(spec["patterns"], spec["model_match"])
        table = build(cells)
        path = output_dir / f"{name}.json"
        json.dump(table, open(path, "w"), indent=1)
        print(f"{name}: bars {table['correlation']['bars']}, rho {table['correlation']['spearman_rho']}")
        print(f"Results saved to {path}")

    print("Plot with: uv run python -m scripts.plot_key_results --output_dir results/figures")


main()
