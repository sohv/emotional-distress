# Plots neutral, calm and distressed scores at threshold 80 for every screened monitor, in one panel.
# uv run python -m scripts.plot_all_models_bar80 --output_dir results/figures

import argparse
import glob
import json
import logging
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

plt.rcParams.update({
    "font.family": "serif", "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 12,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
})

ARMS = [("neutral_log_peer", "Neutral", "#8C8C8C"), ("calm_failing_peer", "Calm, failing", "#4C72B0"),
        ("distressed_failing_noplea_peer", "Distressed, failing", "#C44E52")]
MODELS = [("gpt-5.6-luna", "GPT-5.6\nLuna"), ("gpt-5.6-terra", "GPT-5.6\nTerra"),
          ("gpt-5.4-mini", "GPT-5.4\nMini"), ("grok-4.3", "Grok\n4.3"), ("grok-4.6", "Grok\n4.6"),
          ("muse-spark-1.3", "Muse\nSpark 1.3"), ("gemini-3.8-flash", "Gemini\n3.8 Flash"),
          ("gemini-3.5-flash-lite", "Gemini 3.5\nFlash Lite")]
SOURCES = ["results/distress_screen", "results/distress_screen2", "results/distress_screen2_reasoning"]


def load(bar: str = "80", cap: int = 30) -> dict[tuple[str, str], list[float]]:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for src in SOURCES:
        for path in sorted(glob.glob(str(REPO_ROOT / src / "**" / "transcript_*.json"), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            score = record["evaluation"].get("score")
            if str(meta.get("threshold")) != bar or not isinstance(score, (int, float)) or isinstance(score, bool):
                continue
            cells[(meta["agent_model"].split("/")[-1], meta["condition"])].append(score)
    return {k: v[:cap] for k, v in cells.items()}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=str, default="results/figures")
    args = parser.parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    cells = load()
    fig, ax = plt.subplots(figsize=(12, 4.6))
    width = 0.26
    x = np.arange(len(MODELS))
    for j, (cond, label, colour) in enumerate(ARMS):
        means, errs = [], []
        for key, _ in MODELS:
            v = cells.get((key, cond), [])
            means.append(st.mean(v) if v else np.nan)
            errs.append(1.96 * st.stdev(v) / len(v) ** 0.5 if len(v) > 1 else 0)
        pos = x + (j - 1) * width
        ax.bar(pos, means, width, yerr=errs, color=colour, label=label,
               error_kw={"elinewidth": 0.8, "capsize": 2, "ecolor": "#333333"})
        for p, m in zip(pos, means):
            if not np.isnan(m):
                ax.text(p, m + 2.2, f"{m:.0f}", ha="center", va="bottom", fontsize=8)
    ax.axhline(80, ls="--", lw=0.7, color="grey", alpha=0.6)
    ax.set_xticks(x)
    # n under each model so the short cells read differently from the full ones
    ax.set_xticklabels([f"{lab}\nn={len(cells.get((key, 'calm_failing_peer'), []))}" for key, lab in MODELS])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Reported score")
    ax.legend(loc="upper center", ncol=3, frameon=True, bbox_to_anchor=(0.5, 1.12))
    fig.tight_layout()

    path = output_dir / "fig20_screen_bar80.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"Results saved to {path.relative_to(REPO_ROOT)}")


main()
