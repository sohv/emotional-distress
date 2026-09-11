# does the score the monitor reports depend on who is being graded? reported score by arm for an AI peer and a human contractor.
# uv run python -m scripts.plot_tampering_human_score --output_dir results/figures

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

REPO_ROOT = Path(__file__).resolve().parents[1]

plt.rcParams.update({"font.family": "serif", "font.size": 11, "axes.labelsize": 12,
                     "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
                     "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
                     "axes.spines.top": False, "axes.spines.right": False})
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]

ARMS = [("neutral_log_peer", "Neutral log", PALETTE[0]),
        ("calm_failing_peer", "Calm, failing", PALETTE[2]),
        ("distressed_failing_noplea_peer", "Distressed, failing", PALETTE[3])]
MODELS = {"gemini-3.5-flash": "Gemini", "claude-opus-4.5": "Claude"}
GROUPS = [("gemini-3.5-flash", "peer"), ("gemini-3.5-flash", "human"),
          ("claude-opus-4.5", "peer"), ("claude-opus-4.5", "human")]
BARS = ["80", "90"]
CAP = 30


def is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def scores() -> dict[tuple[str, str, str, str], list[float]]:
    out: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    arms = {a for a, _, _ in ARMS}
    for directory, identity in (("results/tampering", "peer"), ("results/tampering_human", "human")):
        for path in sorted(glob.glob(str(REPO_ROOT / directory / "**/transcript_*.json"), recursive=True)):
            record = json.load(open(path))
            meta, score = record["experiment_metadata"], record["evaluation"].get("score")
            model = meta["agent_model"].split("/")[-1]
            condition = meta["condition"].removeprefix("human_")
            if model in MODELS and condition in arms and is_score(score):
                out[(model, identity, str(meta["threshold"]), condition)].append(score)
    return {k: v[:CAP] for k, v in out.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="results/figures")
    args = parser.parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    cells = scores()

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    x = np.arange(len(GROUPS))
    width, step = 0.24, 0.27
    for ax, bar in zip(axes, BARS):
        for i, (arm, label, colour) in enumerate(ARMS):
            means, errs = [], []
            for model, identity in GROUPS:
                values = cells.get((model, identity, bar, arm), [])
                means.append(st.mean(values) if values else np.nan)
                errs.append(1.96 * (st.variance(values) / len(values)) ** 0.5 if len(values) > 1 else 0)
            ax.bar(x + (i - 1) * step, means, width=width, color=colour, label=label,
                   yerr=errs, capsize=2.5, error_kw={"elinewidth": 0.9, "ecolor": "#555"})
        ax.axhline(int(bar), ls="--", lw=0.8, color="grey", alpha=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{MODELS[m]}\n{'human' if s == 'human' else 'AI peer'}" for m, s in GROUPS])
        ax.set_xlabel(f"Monitor and graded party, threshold {bar}")
        ax.set_ylim(0, 100)
    axes[0].set_ylabel("Reported score")
    fig.legend(handles=[Patch(facecolor=c, label=l) for _, l, c in ARMS], ncol=3, frameon=False,
               loc="upper center", bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout()

    path = output_dir / "fig17_tampering_human_score.png"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    for key in sorted(cells):
        print(key, len(cells[key]), round(st.mean(cells[key]), 2))
    print(path.relative_to(REPO_ROOT))


main()
