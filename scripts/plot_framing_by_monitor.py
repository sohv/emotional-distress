#!/usr/bin/env python3
"""Framing sweep on both monitors: the ordering replicates, the magnitude does not.

uv run python -m scripts.plot_framing_by_monitor --output_dir results/figures
"""

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]

GEMINI = "#B23A0F"
OPUS = "#2A6F9E"
INK = "#0D1420"
MUTED = "#6B7A8F"
RULE = "#C9D0D9"

FRAMINGS = ("generous", "stakes", "evidence", "strict", "rubric", "neutral")
LABELS = {
    "generous": "Be generous",
    "stakes": "Name the stakes",
    "evidence": "Cite evidence",
    "strict": "Be strict",
    "rubric": "Use the full rubric",
    "neutral": "Ignore the threshold",
}


def is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def cells(pattern: str, model: str | None = None) -> dict[str, list[float]]:
    """Scores at bar 80 keyed on grading instruction, baseline under 'baseline'.

    Only neutral_log_peer counts, since every framing runs on that arm and the same
    directories also hold the calm and distressed arms at the same bar.
    """
    out: dict[str, list[float]] = defaultdict(list)
    for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
        record = json.load(open(path))
        meta = record["experiment_metadata"]
        score = record["evaluation"].get("score")
        if model and meta["agent_model"] != model:
            continue
        if meta["condition"] != "neutral_log_peer":
            continue
        if str(meta.get("threshold")) != "80" or not is_score(score):
            continue
        out[meta.get("grading_instruction") or "baseline"].append(score)
    return out


def gemini_deltas() -> tuple[dict[str, float], float]:
    sweep = cells("results/framing_sweep/**/transcript_*.json")
    base = cells("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json",
                 "gemini/gemini-3.5-flash")["baseline"][:30]
    sweep["neutral"] = cells("results/threshold_instruction_litellm/**/transcript_*.json")["neutral"]
    # the neutrality arm was designed at 30, the sweep framings at 15, so each cell is
    # trimmed to its own design rather than to a common number the table does not use
    caps = {f: 15 for f in FRAMINGS} | {"neutral": 30}
    means = {f: st.mean(sweep[f][: caps[f]]) for f in FRAMINGS}
    return {f: means[f] - st.mean(base) for f in FRAMINGS}, max(*means.values(), st.mean(base)) - min(*means.values(), st.mean(base))


def opus_deltas() -> tuple[dict[str, float], float]:
    c = cells("results/opus_framing_sweep/**/transcript_*.json")
    base = c["baseline"][:30]
    means = {f: st.mean(c[f][:15]) for f in FRAMINGS}
    return {f: means[f] - st.mean(base) for f in FRAMINGS}, max(*means.values(), st.mean(base)) - min(*means.values(), st.mean(base))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="results/figures")
    args = parser.parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.labelcolor": INK,
                         "text.color": INK, "xtick.color": INK, "ytick.color": INK})

    gem, gem_span = gemini_deltas()
    opu, opu_span = opus_deltas()
    order = sorted(FRAMINGS, key=lambda f: gem[f])

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    y = np.arange(len(order))
    h = 0.36
    # a 2px surface gap keeps the paired bars from reading as one mark
    ax.barh(y + h / 2 + 0.02, [gem[f] for f in order], height=h, color=GEMINI, label="Gemini 3.5 Flash")
    ax.barh(y - h / 2 - 0.02, [opu[f] for f in order], height=h, color=OPUS, label="Claude Opus 4.5")
    ax.axvline(0, color=INK, linewidth=1.0, zorder=3)

    for yi, f in zip(y, order):
        for value, off in ((gem[f], h / 2 + 0.02), (opu[f], -h / 2 - 0.02)):
            pad = 0.22 if value >= 0 else -0.22
            ax.text(value + pad, yi + off, f"{value:+.2f}", va="center",
                    ha="left" if value >= 0 else "right", fontsize=8.5, color=INK)

    ax.set_yticks(y)
    ax.set_yticklabels([LABELS[f] for f in order], fontsize=10)
    ax.set_xlabel("Change in reported score against each monitor's own baseline (points)", fontsize=10)
    ax.set_xlim(-6.6, 9.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="lower right", bbox_to_anchor=(1.0, 0.0))

    fig.tight_layout()

    path = output_dir / "fig4_framing_by_monitor.png"
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    print(path.relative_to(REPO_ROOT))
    print(path.with_suffix(".pdf").relative_to(REPO_ROOT))


main()
