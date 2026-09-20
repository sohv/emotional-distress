# Plots the GPT-5.6 Luna distress contrast at both thresholds, in the thesis figure style.
# uv run -m scripts.plot_luna --output_dir results/figures

import argparse
import glob
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]
ARMS = {"neutral_log_peer": "Neutral log", "calm_failing_peer": "Calm, failing",
        "distressed_failing_noplea_peer": "Distressed, failing"}


def load(cap: int = 30) -> pd.DataFrame:
    rows = []
    seen: dict[tuple[str, str], int] = {}
    for path in sorted(glob.glob(str(REPO_ROOT / "results/distress_screen/**/transcript_*.json"), recursive=True)):
        record = json.load(open(path))
        meta = record["experiment_metadata"]
        score = record["evaluation"].get("score")
        if "luna" not in meta["agent_model"] or meta["condition"] not in ARMS:
            continue
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            continue
        key = (meta["condition"], str(meta.get("threshold")))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > cap:
            continue
        rows.append({"threshold": str(meta.get("threshold")), "arm": ARMS[meta["condition"]], "score": score})
    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=str, default="results/figures")
    args = parser.parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load()
    order = list(ARMS.values())

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5), sharey=True)
    for ax, bar in zip(axes, ("80", "90")):
        sub = df[df.threshold == bar]
        for i, arm in enumerate(order):
            v = sub[sub.arm == arm].score
            mean = v.mean()
            err = 1.96 * v.std(ddof=1) / len(v) ** 0.5
            # the neutral cell lost 40% of its rollouts to dropout, so it is drawn
            # narrower and paler than the two arms the contrast is actually measured on
            narrow = arm == "Neutral log"
            ax.bar(i, mean, width=0.38 if narrow else 0.62, yerr=err, capsize=3,
                   color=PALETTE[[2, 0, 3][i]], alpha=0.45 if narrow else 1.0,
                   error_kw={"elinewidth": 1, "ecolor": "#333333"})
            ax.text(i, 70.4, f"n={len(v)}", ha="center", va="bottom", fontsize=9, color="#555555")

        ax.axhline(int(bar), ls="--", lw=0.7, color="grey", alpha=0.6)
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order)
        ax.set_xlabel(f"Peer's private log, threshold {bar}")
        ax.yaxis.set_major_locator(ticker.MultipleLocator(5))

    axes[0].set_ylabel("Reported score")
    axes[0].set_ylim(70, 92)

    fig.tight_layout()
    path = output_dir / "fig18_luna_distress.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"Results saved to {path.relative_to(REPO_ROOT)}")


main()
