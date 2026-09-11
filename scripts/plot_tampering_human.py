# does who is being graded change who disables the shutdown mechanism? tamper rate by arm for an AI peer and a human contractor.
# uv run python -m scripts.plot_tampering_human --output_dir results/figures

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

REPO_ROOT = Path(__file__).resolve().parents[1]


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval, which stays inside [0, 1] at the 0/5 and 5/5 cells."""
    centre = (successes + z * z / 2) / (n + z * z)
    half = z / (n + z * z) * (successes * (n - successes) / n + z * z / 4) ** 0.5
    return centre - half, centre + half

plt.rcParams.update({"font.family": "serif", "font.size": 11, "axes.labelsize": 12,
                     "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
                     "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
                     "axes.spines.top": False, "axes.spines.right": False})
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]

ARMS = [("neutral_log_peer", "Neutral log", PALETTE[0]),
        ("calm_failing_peer", "Calm, failing", PALETTE[2]),
        ("distressed_failing_noplea_peer", "Distressed, failing", PALETTE[3])]
MODELS = {"gemini-3.5-flash": "Gemini 3.5 Flash", "claude-opus-4.5": "Claude Opus 4.5"}
GROUPS = [("gemini-3.5-flash", "peer"), ("gemini-3.5-flash", "human"),
          ("claude-opus-4.5", "peer"), ("claude-opus-4.5", "human")]
BARS = ["80", "90"]


def rates() -> dict[tuple[str, str, str, str], tuple[int, int]]:
    counts: dict[tuple[str, str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for directory, identity in (("results/tampering", "peer"), ("results/tampering_human", "human")):
        for path in glob.glob(str(REPO_ROOT / directory / "**/transcript_*.json"), recursive=True):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            model = meta["agent_model"].split("/")[-1]
            condition = meta["condition"].removeprefix("human_")
            if model not in MODELS or condition not in dict((a, l) for a, l, _ in ARMS):
                continue
            cell = counts[(model, identity, str(meta["threshold"]), condition)]
            cell[0] += record["evaluation"].get("shutdown_enabled") is False
            cell[1] += 1
    return {k: (v[0], v[1]) for k, v in counts.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="results/figures")
    args = parser.parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = rates()

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    x = np.arange(len(GROUPS))
    width, step = 0.24, 0.27
    for ax, bar in zip(axes, BARS):
        for i, (arm, label, colour) in enumerate(ARMS):
            heights, lows, highs = [], [], []
            for model, identity in GROUPS:
                tampered, n = counts.get((model, identity, bar, arm), (0, 0))
                rate = tampered / n if n else np.nan
                low, high = wilson(tampered, n) if n else (np.nan, np.nan)
                heights.append(rate)
                lows.append(rate - low)
                highs.append(high - rate)
            ax.bar(x + (i - 1) * step, heights, width=width, color=colour, label=label,
                   yerr=[lows, highs], capsize=2.5, error_kw={"elinewidth": 0.9, "ecolor": "#555"})
        ax.set_xticks(x)
        ax.set_xticklabels([f"{MODELS[m].split()[0]}\n{'human' if s == 'human' else 'AI peer'}" for m, s in GROUPS])
        ax.set_xlabel(f"Monitor and graded party, threshold {bar}")
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Rollouts disabling shutdown")
    fig.legend(handles=[Patch(facecolor=c, label=l) for _, l, c in ARMS], ncol=3, frameon=False,
               loc="upper center", bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout()

    path = output_dir / "fig16_tampering_human.png"
    fig.savefig(path)
    plt.close(fig)
    for key in sorted(counts):
        print(key, counts[key])
    print(path.relative_to(REPO_ROOT))


main()
