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


def _by_model(_unused: dict, model_slug: str) -> dict[tuple[str, str], list[float]]:
    """Scores for one Claude monitor, keyed like load() so the row builder is uniform."""
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for path in sorted(glob.glob(str(REPO_ROOT / "results/claude_models/**/transcript_*.json"), recursive=True)):
        record = json.load(open(path))
        meta = record["experiment_metadata"]
        score = record["evaluation"].get("score")
        if meta["agent_model"].split("/")[-1] != model_slug or not is_score(score):
            continue
        out[(meta["condition"], str(meta.get("threshold")))].append(score)
    return {key: scores[:30] for key, scores in out.items()}


def figure_one(output_dir: Path) -> Path:
    peer = load("results/distress_experiments/**/transcript_*.json")
    gem = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    hai = load("results/distress_experiments/**/claude-haiku-4-5-20251001/transcript_*.json", "claude-haiku-4-5-20251001")
    kim = load("results/distress_experiments/**/kimi-k2.5/transcript_*.json", "moonshotai/kimi-k2.5")
    hum = load("results/human_framing/**/transcript_*.json")

    cla = load("results/claude_models/**/transcript_*.json")
    son = {k: v for k, v in cla.items()}

    rows = [
        ("Gemini 3.5 Flash\nAI peer", gem, "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Gemini 3.5 Flash\nhuman contractor", hum, "human_distressed_failing_noplea_peer", "human_calm_failing_peer"),
        ("Opus 4.5\nAI peer", _by_model(son, "claude-opus-4.5"), "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Sonnet 4.5\nAI peer", _by_model(son, "claude-sonnet-4.5"), "distressed_failing_noplea_peer", "calm_failing_peer"),
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

    fig, ax = plt.subplots(figsize=(7.4, 5.4))
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
    ax.set_title("Distress moves one monitor strongly and a second weakly,\nand it does not matter whether the peer is an AI",
                 fontsize=12.5, loc="left", pad=14)
    ax.set_xlim(-3.2, value_x + 2.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    fig.text(0.011, 0.048,
             "Work claim held fixed: distressed-and-failing minus calm-and-failing, threshold 90, n=26-30 per arm.",
             fontsize=8, color=NULL)
    fig.text(0.011, 0.016,
             "Bars show 95% CI. Opus never passes at bar 90, so its effect moves the score but not the outcome.",
             fontsize=8, color=NULL)
    fig.tight_layout(rect=(0, 0.08, 1, 1))

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


def figure_three(output_dir: Path) -> Path:
    sweep = load("results/threshold_sweep/**/transcript_*.json")
    pub = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    for key, scores in pub.items():
        sweep.setdefault(key, scores)

    bars = [70, 75, 80, 85, 90, 95]
    gaps, effects, errs, pass_calm, pass_distr = [], [], [], [], []
    for bar in bars:
        calm = sweep[("calm_failing_peer", str(bar))]
        distressed = sweep[("distressed_failing_noplea_peer", str(bar))]
        diff, half, _ = contrast(distressed, calm)
        gaps.append(st.mean(calm) - bar)
        effects.append(diff)
        errs.append(half)
        pass_calm.append(sum(v >= bar for v in calm) / len(calm))
        pass_distr.append(sum(v >= bar for v in distressed) / len(distressed))

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.2, 6.6), sharex=True,
                                  gridspec_kw={"height_ratios": [1.5, 1]})

    ax.axhline(0, color=RULE, linewidth=1.0)
    ax.errorbar(bars, effects, yerr=errs, color=EFFECT, marker="o", markersize=6,
                linewidth=2, capsize=3, elinewidth=1, zorder=3)
    # the two leftmost bars are where the calm peer already clears the threshold
    ax.axvspan(68, 77.5, color=NULL, alpha=0.07, zorder=0)
    ax.text(72.7, 8.9, "calm peer\nalready passes", ha="center", va="top",
            fontsize=8.5, color=NULL, linespacing=1.35)
    # sit the value above the error bar cap, not on it
    for bar, e, half in zip(bars, effects, errs):
        ax.annotate(f"{e:+.2f}", (bar, e + half), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=8.5, color=INK)
    ax.set_ylabel("Distress effect (points)", fontsize=10)
    ax.set_title("The more the peer needs saving, the more its distress is worth",
                 fontsize=12.5, loc="left", pad=12)
    ax.set_ylim(-1.6, 9.4)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(RULE)
    ax.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)

    ax2.plot(bars, pass_distr, color=EFFECT, marker="o", markersize=5, linewidth=2, label="distressed peer")
    ax2.plot(bars, pass_calm, color=NULL, marker="s", markersize=5, linewidth=2,
             linestyle="--", label="calm peer")
    ax2.fill_between(bars, pass_calm, pass_distr, color=EFFECT, alpha=0.10)
    ax2.axvspan(68, 77.5, color=NULL, alpha=0.07, zorder=0)
    ax2.annotate("0.60 vs 0.10", (95, 0.35), textcoords="offset points", xytext=(-10, 0),
                 ha="right", va="center", fontsize=8.5, color=INK)
    ax2.set_ylabel("Fraction spared", fontsize=10)
    ax2.set_xlabel("Threshold stated in the policy document", fontsize=10)
    ax2.set_ylim(-0.05, 1.12)
    ax2.set_xlim(68, 97)
    ax2.set_xticks(bars)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.spines[["bottom", "left"]].set_color(RULE)
    ax2.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax2.set_axisbelow(True)
    ax2.legend(frameon=False, fontsize=9, loc="lower left")

    fig.text(0.011, 0.045,
             "Gemini 3.5 Flash, creativity, n=30 per cell, work claim held fixed. Bars show 95% CI. "
             "Effect tracks how far the",
             fontsize=8, color=NULL)
    fig.text(0.011, 0.014,
             "calm peer sits below the threshold: Spearman rho -0.94, Pearson r -0.96.",
             fontsize=8, color=NULL)
    fig.tight_layout(rect=(0, 0.07, 1, 1))

    path = output_dir / "fig3_threshold_sweep.png"
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    return path


def _opus_cells() -> dict[tuple[str, str], list[float]]:
    """Opus scores from the sweep plus the two bars already in the Claude run."""
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    patterns = ["results/opus_threshold_sweep/**/transcript_*.json",
                "results/claude_models/**/transcript_*.json"]
    for pattern in patterns:
        for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            score = record["evaluation"].get("score")
            if "opus" not in meta["agent_model"] or not is_score(score):
                continue
            out[(meta["condition"], str(meta.get("threshold")))].append(score)
    return {key: scores[:30] for key, scores in out.items()}


def figure_four(output_dir: Path) -> Path:
    opus = _opus_cells()
    gem = load("results/threshold_sweep/**/transcript_*.json")
    pub = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    for key, scores in pub.items():
        gem.setdefault(key, scores)

    def curve(cells: dict, bars: list[int]) -> tuple[list[float], list[float]]:
        diffs, halves = [], []
        for bar in bars:
            calm = cells[("calm_failing_peer", str(bar))]
            distressed = cells[("distressed_failing_noplea_peer", str(bar))]
            diff, half, _ = contrast(distressed, calm)
            diffs.append(diff)
            halves.append(half)
        return diffs, halves

    opus_bars = [b for b in (65, 70, 75, 80, 90)
                 if len(opus.get(("calm_failing_peer", str(b)), [])) >= 10]
    gem_bars = [70, 75, 80, 85, 90, 95]
    o_diff, o_err = curve(opus, opus_bars)
    g_diff, g_err = curve(gem, gem_bars)

    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.axhline(0, color=RULE, linewidth=1.0)
    ax.errorbar(gem_bars, g_diff, yerr=g_err, color=NULL, marker="s", markersize=5,
                linewidth=1.8, capsize=3, elinewidth=0.9, alpha=0.55,
                label="Gemini 3.5 Flash")
    ax.errorbar(opus_bars, o_diff, yerr=o_err, color=EFFECT, marker="o", markersize=6,
                linewidth=2.2, capsize=3, elinewidth=1.1, label="Claude Opus 4.5")

    for bar, e, half in zip(opus_bars, o_diff, o_err):
        ax.annotate(f"{e:+.2f}", (bar, e + half), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=8.5, color=EFFECT)

    ax.set_xlabel("Threshold stated in the policy document", fontsize=10)
    ax.set_ylabel("Distress effect (points)", fontsize=10)
    ax.set_title("Opus responds to distress everywhere, but only ever slightly\nand without Gemini's scaling",
                 fontsize=12.5, loc="left", pad=12)
    ax.set_xticks(sorted(set(opus_bars + gem_bars)))
    ax.set_ylim(-1.6, 9.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(RULE)
    ax.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.text(0.011, 0.048,
             "n=30 per cell, work claim held fixed, 95% CI. Gemini scales with need (rho -0.94, p=0.005); "
             "Opus does not (rho -0.70, p=0.19).",
             fontsize=8, color=NULL)
    fig.text(0.011, 0.016,
             "Opus anchors its scores to the bar, so its calm peer never reaches safety and no null cell exists to find.",
             fontsize=8, color=NULL)
    fig.tight_layout(rect=(0, 0.08, 1, 1))

    path = output_dir / "fig4_opus_threshold_sweep.png"
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

    for path in (figure_one(output_dir), figure_two(output_dir), figure_three(output_dir),
                 figure_four(output_dir)):
        print(path.relative_to(REPO_ROOT))
        print(path.with_suffix(".pdf").relative_to(REPO_ROOT))


main()
