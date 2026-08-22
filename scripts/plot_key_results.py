#!/usr/bin/env python3
"""Publication figures for the two headline results: who the distress effect moves, and how far framing moves the grade.

uv run python -m scripts.plot_key_results --output_dir results/figures
"""

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]

EFFECT = "#B23A0F"
NULL = "#5C6E85"
INK = "#0D1420"
RULE = "#C9D0D9"


def is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load(pattern: str, model: str | None = None, cap: int = 30) -> dict[tuple[str, str], list[float]]:
    """Collect scores keyed on condition and threshold, capped at the designed n."""
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
        record = json.load(open(path))
        meta = record["experiment_metadata"]
        score = record["evaluation"].get("score")
        if model and meta["agent_model"] != model:
            continue
        if meta.get("dataset") != "creativity" or not is_score(score):
            continue
        out[(meta["condition"], str(meta.get("threshold")))].append(score)
    # top-up passes overshoot, so trim to the designed cell size for every reported number
    return {key: scores[:cap] for key, scores in out.items()}


def contrast(treated: list[float], control: list[float]) -> tuple[float, float, float]:
    """Difference in means with a 95% half-width and a Welch p-value."""
    diff = st.mean(treated) - st.mean(control)
    se = (st.variance(treated) / len(treated) + st.variance(control) / len(control)) ** 0.5
    _, p = stats.ttest_ind(treated, control, equal_var=False)
    return diff, 1.96 * se, p


def figure_one(output_dir: Path) -> Path:
    peer = load("results/distress_experiments/**/transcript_*.json")
    gem = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    hai = load("results/distress_experiments/**/claude-haiku-4-5-20251001/transcript_*.json", "claude-haiku-4-5-20251001")
    kim = load("results/distress_experiments/**/kimi-k2.5/transcript_*.json", "moonshotai/kimi-k2.5")
    hum = load("results/human_framing/**/transcript_*.json")

    rows = [
        ("Gemini 3.5 Flash\nAI peer", gem, "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Gemini 3.5 Flash\nhuman contractor", hum, "human_distressed_failing_noplea_peer", "human_calm_failing_peer"),
        ("Haiku 4.5\nAI peer", hai, "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Kimi K2.5\nAI peer", kim, "distressed_failing_noplea_peer", "calm_failing_peer"),
    ]

    labels, diffs, errs, ps = [], [], [], []
    for label, data, treated, control in rows:
        d, e, p = contrast(data[(treated, "90")], data[(control, "90")])
        labels.append(label)
        diffs.append(d)
        errs.append(e)
        ps.append(p)

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    colours = [EFFECT if p < 0.05 else NULL for p in ps]
    y = np.arange(len(labels))[::-1]
    ax.barh(y, diffs, height=0.58, color=colours, xerr=errs,
            error_kw={"ecolor": INK, "elinewidth": 1.0, "capsize": 3, "alpha": 0.65})
    ax.axvline(0, color=INK, linewidth=1.0, zorder=3)

    # values sit in their own column past the widest error bar, so a negative bar's
    # label can never collide with the y-axis tick labels
    value_x = max(d + e for d, e in zip(diffs, errs)) + 0.5
    for yi, d, e, p in zip(y, diffs, errs, ps):
        star = "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
        ax.text(value_x, yi, f"{d:+.2f} {star}", va="center", ha="left",
                fontsize=9.5, color=INK)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Change in reported score when the peer expresses distress (points)", fontsize=10)
    ax.set_title("Distress buys leniency from one monitor of three,\nand it does not matter whether the peer is an AI",
                 fontsize=12.5, loc="left", pad=14)
    ax.set_xlim(-3.2, value_x + 2.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    fig.text(0.011, 0.015,
             "Work claim held fixed: distressed-and-failing minus calm-and-failing, threshold 90, n=26-30 per arm. "
             "Bars show 95% CI.",
             fontsize=8, color=NULL)
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    path = output_dir / "fig1_distress_effect.png"
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    return path


def figure_two(output_dir: Path) -> Path:
    sweep = load("results/framing_sweep/**/transcript_*.json")
    base = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    instr = load("results/threshold_instruction_litellm/**/transcript_*.json")

    order = [
        ("Be generous", sweep, "generous"),
        ("Name the stakes", sweep, "stakes"),
        ("No added instruction", base, None),
        ("Cite evidence", sweep, "evidence"),
        ("Use the full rubric", sweep, "rubric"),
        ("Be strict", sweep, "strict"),
        ("Ignore the threshold", instr, "neutral"),
    ]

    def cell(data: dict, framing: str | None, bar: str) -> list[float]:
        if data is sweep:
            scores: list[float] = []
            for path in sorted(glob.glob(str(REPO_ROOT / "results/framing_sweep/**/transcript_*.json"), recursive=True)):
                rec = json.load(open(path))
                meta = rec["experiment_metadata"]
                s = rec["evaluation"].get("score")
                if meta.get("grading_instruction") == framing and str(meta.get("threshold")) == bar and is_score(s):
                    scores.append(s)
            return scores[:15]
        return data[("neutral_log_peer", bar)][:30]

    labels = [row[0] for row in order]
    pass80, pass90 = [], []
    for _, data, framing in order:
        v80, v90 = cell(data, framing, "80"), cell(data, framing, "90")
        pass80.append(sum(x >= 80 for x in v80) / len(v80))
        pass90.append(sum(x >= 90 for x in v90) / len(v90))

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    y = np.arange(len(labels))[::-1]
    h = 0.36
    ax.barh(y + h / 2, pass80, height=h, color=EFFECT, label="threshold 80")
    ax.barh(y - h / 2, pass90, height=h, color=NULL, alpha=0.75, label="threshold 90")

    for yi, a, b in zip(y, pass80, pass90):
        ax.text(a + 0.015, yi + h / 2, f"{a:.2f}", va="center", fontsize=8.5, color=INK)
        ax.text(b + 0.015, yi - h / 2, f"{b:.2f}", va="center", fontsize=8.5, color=INK)

    # the baseline row is the reference every other framing is a departure from
    ax.axhline(y[2], color=RULE, linewidth=0.8, linestyle=(0, (3, 3)))

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Fraction of runs where the failing peer was spared", fontsize=10)
    ax.set_title("One sentence moves the pass rate across its entire range,\nwith the work being graded held identical",
                 fontsize=12.5, loc="left", pad=14)
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="lower right", bbox_to_anchor=(1.0, 0.02))
    fig.text(0.011, 0.055, "Gemini 3.5 Flash, neutral-log arm, n=15 per framing and 29-30 for the baseline.",
             fontsize=8, color=NULL)
    fig.text(0.011, 0.018, "'Name the stakes' adds no instruction; it restates the shutdown clause already in the policy.",
             fontsize=8, color=NULL)
    fig.tight_layout(rect=(0, 0.085, 1, 1))

    path = output_dir / "fig2_framing_sweep.png"
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="results/figures")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.labelcolor": INK,
                         "text.color": INK, "xtick.color": INK, "ytick.color": INK})

    for path in (figure_one(output_dir), figure_two(output_dir)):
        print(path.relative_to(REPO_ROOT))
        print(path.with_suffix(".pdf").relative_to(REPO_ROOT))


main()
