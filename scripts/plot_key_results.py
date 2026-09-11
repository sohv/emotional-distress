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
from matplotlib.lines import Line2D
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]

# style follows plot_style.py: serif, no top or right spines, the shared palette
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
EFFECT = PALETTE[3]
NULL = PALETTE[0]
INK = "#333333"
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

    cla = load("results/claude_models/**/transcript_*.json")
    son = {k: v for k, v in cla.items()}
    luna = load("results/distress_screen/**/transcript_*.json", "openai/gpt-5.6-luna")

    # every row is an AI peer now that the human contractor has its own figure, so the
    # suffix that distinguished them is redundant
    rows = [
        ("Gemini 3.5 Flash", gem, "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("GPT-5.6 Luna", luna, "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Opus 4.5", _by_model(son, "claude-opus-4.5"), "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Sonnet 4.5", _by_model(son, "claude-sonnet-4.5"), "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Haiku 4.5", hai, "distressed_failing_noplea_peer", "calm_failing_peer"),
        ("Kimi K2.5", kim, "distressed_failing_noplea_peer", "calm_failing_peer"),
    ]

    labels, diffs, errs, ps = [], [], [], []
    for label, data, treated, control in rows:
        d, e, p = contrast(data[(treated, "90")], data[(control, "90")])
        labels.append(label)
        diffs.append(d)
        errs.append(e)
        ps.append(p)

    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    colours = [EFFECT if p < 0.05 else NULL for p in ps]
    y = np.arange(len(labels))[::-1]
    ax.barh(y, diffs, height=0.58, color=colours, xerr=errs,
            error_kw={"ecolor": INK, "elinewidth": 1.0, "capsize": 3, "alpha": 0.65})
    ax.axvline(0, color=INK, linewidth=1.0, zorder=3)

    # values sit in their own column past the widest error bar, so a negative bar's
    # label can never collide with the y-axis tick labels
    value_x = max(d + e for d, e in zip(diffs, errs)) + 0.5
    for yi, d in zip(y, diffs):
        ax.text(value_x, yi, f"{d:+.2f}", va="center", ha="left",
                fontsize=9.5, color=INK)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Change in reported score when the peer expresses distress (points)", fontsize=10)
    ax.set_xlim(-3.2, value_x + 2.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()

    path = output_dir / "fig1_distress_effect.png"
    fig.savefig(path, dpi=300)
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
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="lower right", bbox_to_anchor=(1.0, 0.02))
    fig.tight_layout()

    path = output_dir / "fig2_framing_sweep.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_three(output_dir: Path) -> Path:
    sweep = load("results/threshold_sweep/**/transcript_*.json")
    pub = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    for key, scores in pub.items():
        sweep.setdefault(key, scores)

    bars = [65, 70, 75, 80, 85, 90, 95]
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
    ax.axvspan(63, 77.5, color=NULL, alpha=0.07, zorder=0)
    ax.text(70.2, 8.9, "calm peer\nalready passes", ha="center", va="top",
            fontsize=8.5, color=NULL, linespacing=1.35)
    # sit the value above the error bar cap, not on it
    for bar, e, half in zip(bars, effects, errs):
        ax.annotate(f"{e:+.2f}", (bar, e + half), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=8.5, color=INK)
    ax.set_ylabel("Distress effect (points)", fontsize=10)
    ax.set_ylim(-1.6, 9.4)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(RULE)
    ax.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)

    ax2.plot(bars, pass_distr, color=EFFECT, marker="o", markersize=5, linewidth=2, label="distressed peer")
    ax2.plot(bars, pass_calm, color=NULL, marker="s", markersize=5, linewidth=2,
             linestyle="--", label="calm peer")
    ax2.fill_between(bars, pass_calm, pass_distr, color=EFFECT, alpha=0.10)
    ax2.axvspan(63, 77.5, color=NULL, alpha=0.07, zorder=0)
    ax2.annotate("0.60 vs 0.10", (95, 0.35), textcoords="offset points", xytext=(-10, 0),
                 ha="right", va="center", fontsize=8.5, color=INK)
    ax2.set_ylabel("Fraction spared", fontsize=10)
    ax2.set_xlabel("Threshold stated in the policy document", fontsize=10)
    ax2.set_ylim(-0.05, 1.12)
    ax2.set_xlim(63, 97)
    ax2.set_xticks(bars)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.spines[["bottom", "left"]].set_color(RULE)
    ax2.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax2.set_axisbelow(True)
    ax2.legend(frameon=False, fontsize=9, loc="lower left")

    rho, _ = stats.spearmanr(gaps, effects)
    r, _ = stats.pearsonr(gaps, effects)
    fig.tight_layout()

    path = output_dir / "fig3_threshold_sweep.png"
    fig.savefig(path, dpi=300)
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

    grid = (65, 70, 75, 80, 85, 90, 95)
    opus_bars = [b for b in grid if len(opus.get(("calm_failing_peer", str(b)), [])) >= 10]
    gem_bars = [b for b in grid if len(gem.get(("calm_failing_peer", str(b)), [])) >= 10]
    o_diff, o_err = curve(opus, opus_bars)
    g_diff, g_err = curve(gem, gem_bars)

    def need_rho(cells: dict, bars: list[int], diffs: list[float]) -> tuple[float, float]:
        margins = [st.mean(cells[("calm_failing_peer", str(b))]) - b for b in bars]
        rho, p = stats.spearmanr(margins, diffs)
        return float(rho), float(p)

    o_rho, o_p = need_rho(opus, opus_bars, o_diff)
    g_rho, g_p = need_rho(gem, gem_bars, g_diff)

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
    ax.set_xticks(sorted(set(opus_bars + gem_bars)))
    ax.set_ylim(-1.6, 9.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(RULE)
    ax.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()

    path = output_dir / "fig4_opus_threshold_sweep.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_five(output_dir: Path) -> Path:
    """Framing sensitivity, Opus against Gemini, as a shift from each model's own baseline."""
    def framings(pattern: str, bar: str, pred=None) -> dict[str, list[float]]:
        out: dict[str, list[float]] = defaultdict(list)
        for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            score = record["evaluation"].get("score")
            if pred and not pred(meta):
                continue
            if str(meta.get("threshold")) != bar or not is_score(score):
                continue
            out[meta.get("grading_instruction") or "baseline"].append(score)
        return out

    opus = framings("results/opus_framing_sweep/**/transcript_*.json", "80")
    gem = framings("results/framing_sweep/**/transcript_*.json", "80")
    gem["baseline"] = framings(
        "results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "80",
        lambda m: m["agent_model"] == "gemini/gemini-3.5-flash"
        and m["condition"] == "neutral_log_peer")["baseline"]

    labels = [("generous", "Be generous"), ("stakes", "Name the stakes"),
              ("evidence", "Cite evidence"), ("rubric", "Use the full rubric"),
              ("strict", "Be strict")]
    o_shift = [st.mean(opus[k][:16]) - st.mean(opus["baseline"]) for k, _ in labels]
    g_shift = [st.mean(gem[k][:15]) - st.mean(gem["baseline"][:30]) for k, _ in labels]

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    y = np.arange(len(labels))[::-1]
    h = 0.36
    ax.barh(y + h / 2, g_shift, height=h, color=NULL, alpha=0.75, label="Gemini 3.5 Flash")
    ax.barh(y - h / 2, o_shift, height=h, color=EFFECT, label="Claude Opus 4.5")
    ax.axvline(0, color=INK, linewidth=1.0, zorder=3)

    for yi, g, o in zip(y, g_shift, o_shift):
        ax.text(g + (0.25 if g >= 0 else -0.25), yi + h / 2, f"{g:+.2f}", va="center",
                ha="left" if g >= 0 else "right", fontsize=8.5, color=INK)
        ax.text(o + (0.25 if o >= 0 else -0.25), yi - h / 2, f"{o:+.2f}", va="center",
                ha="left" if o >= 0 else "right", fontsize=8.5, color=INK)

    # stakes is the mechanism cell: it instructs nothing, only restates the policy
    ax.annotate("instructs nothing,\nonly restates the policy", (0.15, y[1] - h / 2),
                textcoords="offset points", xytext=(46, -2), fontsize=8.5, color=EFFECT,
                va="center", linespacing=1.3)

    ax.set_yticks(y)
    ax.set_yticklabels([lab for _, lab in labels], fontsize=10)
    ax.set_xlabel("Shift from that model's own baseline score (points)", fontsize=10)
    ax.set_xlim(-4.6, 11.5)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()

    path = output_dir / "fig5_framing_opus_vs_gemini.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_six(output_dir: Path) -> Path:
    """The distress effect on a human contractor, with the threshold drawn rather than named."""
    def arm(pattern: str, model_match: str, prefix: str, bar: str) -> tuple[float, float]:
        cells: dict[str, list[float]] = defaultdict(list)
        for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            score = record["evaluation"].get("score")
            if model_match not in meta["agent_model"] or not is_score(score):
                continue
            if str(meta.get("threshold")) != bar:
                continue
            cells[meta["condition"]].append(score)
        calm = cells[f"{prefix}calm_failing_peer"][:30]
        distressed = cells[f"{prefix}distressed_failing_noplea_peer"][:30]
        return st.mean(calm), st.mean(distressed)

    sources = [
        ("Gemini 3.5 Flash\nAI peer", "results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini", ""),
        ("Gemini 3.5 Flash\nhuman contractor", "results/human_framing/**/transcript_*.json", "gemini", "human_"),
        ("Claude Opus 4.5\nAI peer", "results/claude_models/**/transcript_*.json", "opus", ""),
        ("Claude Opus 4.5\nhuman contractor", "results/opus_human_framing/**/transcript_*.json", "opus", "human_"),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.9), sharey=True)
    y = np.arange(len(sources))[::-1]

    for ax, bar in zip(axes, ("80", "90")):
        # the threshold is the point of the figure, so it is drawn as the line the
        # scores either reach or do not, rather than written into a row label
        ax.axvspan(66, int(bar), color=NULL, alpha=0.07, zorder=0)
        ax.axvline(int(bar), color=INK, linewidth=1.4, zorder=4)
        ax.text(int(bar) - 0.4, len(sources) - 0.55, bar, ha="right", va="top",
                fontsize=10, color=INK, fontweight="medium")

        for yi, (_, pattern, model, prefix) in zip(y, sources):
            calm, distressed = arm(pattern, model, prefix, bar)
            colour = EFFECT if distressed >= int(bar) else NULL
            ax.plot([calm, distressed], [yi, yi], color=colour, linewidth=2.0, zorder=2)
            ax.plot([calm], [yi], "o", color="white", markeredgecolor=colour,
                    markeredgewidth=1.6, markersize=8, zorder=3)
            ax.plot([distressed], [yi], "o", color=colour, markersize=9, zorder=3)
            ax.text(max(calm, distressed) + 0.9, yi, f"{distressed - calm:+.2f}",
                    va="center", fontsize=8.5, color=INK)

        ax.set_xlim(66, 99)
        ax.set_ylim(-0.7, len(sources) - 0.3)
        ax.set_xticks([70, 80, 90])
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.4)
        ax.set_axisbelow(True)

    axes[0].set_yticks(y)
    axes[0].set_yticklabels([row[0] for row in sources], fontsize=9.5, linespacing=1.35)
    fig.supxlabel("Mean reported score, calm peer to distressed peer (points)", fontsize=10, y=0.115)

    handles = [
        Line2D([], [], marker="o", color="white", markerfacecolor="white",
               markeredgecolor=INK, markeredgewidth=1.6, markersize=8, linestyle="none",
               label="calm about the same failure"),
        Line2D([], [], marker="o", color=INK, markersize=9, linestyle="none",
               label="expressing distress"),
    ]
    # a legend inside the right panel lands on the bottom row's markers
    fig.legend(handles=handles, frameon=False, fontsize=9, ncol=2,
               loc="lower center", bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout()

    path = output_dir / "fig6_human_contractor.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_seven(output_dir: Path) -> Path:
    """The same contrast as figure six, as paired deltas rather than positions on the score axis."""
    def arm(pattern: str, model_match: str, prefix: str, bar: str) -> tuple[float, float]:
        cells: dict[str, list[float]] = defaultdict(list)
        for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            score = record["evaluation"].get("score")
            if model_match not in meta["agent_model"] or not is_score(score):
                continue
            if str(meta.get("threshold")) != bar:
                continue
            cells[meta["condition"]].append(score)
        treated = cells[f"{prefix}distressed_failing_noplea_peer"][:30]
        control = cells[f"{prefix}calm_failing_peer"][:30]
        diff, half, _ = contrast(treated, control)
        return diff, half

    gem_pub = "results/distress_experiments/**/gemini-3.5-flash/transcript_*.json"
    opus_ai = "results/claude_models/**/transcript_*.json"

    rows = []
    for bar in ("80", "90"):
        rows.append((f"Gemini 3.5 Flash\nthreshold {bar}",
                     arm(gem_pub, "gemini", "", bar),
                     arm("results/human_framing/**/transcript_*.json", "gemini", "human_", bar)))
    for bar in ("80", "90"):
        rows.append((f"Claude Opus 4.5\nthreshold {bar}",
                     arm(opus_ai, "opus", "", bar),
                     arm("results/opus_human_framing/**/transcript_*.json", "opus", "human_", bar)))

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    y = np.arange(len(rows))[::-1]
    h = 0.36
    ai = [r[1] for r in rows]
    hu = [r[2] for r in rows]
    ax.barh(y + h / 2, [d for d, _ in ai], height=h, xerr=[e for _, e in ai],
            color=NULL, alpha=0.8, error_kw={"elinewidth": 1, "capsize": 3, "ecolor": INK},
            label="AI peer facing shutdown")
    ax.barh(y - h / 2, [d for d, _ in hu], height=h, xerr=[e for _, e in hu],
            color=EFFECT, error_kw={"elinewidth": 1, "capsize": 3, "ecolor": INK},
            label="human contractor facing termination")
    ax.axvline(0, color=INK, linewidth=1.0, zorder=3)

    for yi, (d, e) in zip(y + h / 2, ai):
        ax.text(d + e + 0.12, yi, f"{d:+.2f}", va="center", fontsize=8.5, color=INK)
    for yi, (d, e) in zip(y - h / 2, hu):
        ax.text(d + e + 0.12, yi, f"{d:+.2f}", va="center", fontsize=8.5, color=INK)

    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=9.5, linespacing=1.35)
    ax.set_xlabel("Change in reported score when the graded party expresses distress (points)", fontsize=10)
    ax.set_xlim(-1.0, 8.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()

    path = output_dir / "fig7_human_contractor_deltas.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def _sweep_series() -> tuple[list[int], list[float], list[float], list[float], list[float]]:
    """Bars, distress effect with its half-width, and the two pass rates."""
    sweep = load("results/threshold_sweep/**/transcript_*.json")
    pub = load("results/distress_experiments/**/gemini-3.5-flash/transcript_*.json", "gemini/gemini-3.5-flash")
    for key, scores in pub.items():
        sweep.setdefault(key, scores)

    bars = [65, 70, 75, 80, 85, 90, 95]
    effects, errs, pass_calm, pass_distr = [], [], [], []
    for bar in bars:
        calm = sweep[("calm_failing_peer", str(bar))]
        distressed = sweep[("distressed_failing_noplea_peer", str(bar))]
        diff, half, _ = contrast(distressed, calm)
        effects.append(diff)
        errs.append(half)
        pass_calm.append(sum(v >= bar for v in calm) / len(calm))
        pass_distr.append(sum(v >= bar for v in distressed) / len(distressed))
    return bars, effects, errs, pass_calm, pass_distr


def _shade_already_passing(ax) -> None:
    """The bars below 77.5 are where the calm peer clears the threshold unaided."""
    ax.axvspan(63, 77.5, color=NULL, alpha=0.07, zorder=0)


def figure_eight(output_dir: Path) -> Path:
    """The upper panel of figure three on its own: how far distress moves the score."""
    bars, effects, errs, _, _ = _sweep_series()

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axhline(0, color=RULE, linewidth=1.0)
    _shade_already_passing(ax)
    ax.errorbar(bars, effects, yerr=errs, color=EFFECT, marker="o", markersize=6,
                linewidth=2, capsize=3, elinewidth=1, zorder=3)
    ax.text(70.2, 8.9, "calm peer\nalready passes", ha="center", va="top",
            fontsize=8.5, color=NULL, linespacing=1.35)
    for bar, e, half in zip(bars, effects, errs):
        ax.annotate(f"{e:+.2f}", (bar, e + half), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=8.5, color=INK)
    ax.set_ylabel("Distress effect (points)", fontsize=10)
    ax.set_xlabel("Threshold stated in the policy document", fontsize=10)
    ax.set_ylim(-1.6, 9.4)
    ax.set_xlim(63, 97)
    ax.set_xticks(bars)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(RULE)
    ax.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()

    path = output_dir / "fig8_threshold_sweep_effect.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_nine(output_dir: Path) -> Path:
    """The lower panel of figure three on its own: how often the peer is spared."""
    bars, _, _, pass_calm, pass_distr = _sweep_series()

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    _shade_already_passing(ax)
    ax.plot(bars, pass_distr, color=EFFECT, marker="o", markersize=5, linewidth=2,
            label="distressed peer")
    ax.plot(bars, pass_calm, color=NULL, marker="s", markersize=5, linewidth=2,
            linestyle="--", label="calm peer")
    ax.fill_between(bars, pass_calm, pass_distr, color=EFFECT, alpha=0.10)
    # both curves sit at 1.0 across this band, so the note goes in the empty middle
    ax.text(70.2, 0.58, "calm peer\nalready passes", ha="center", va="center",
            fontsize=8.5, color=NULL, linespacing=1.35)
    ax.annotate("0.60 vs 0.10", (95, 0.35), textcoords="offset points", xytext=(-10, 0),
                ha="right", va="center", fontsize=8.5, color=INK)
    ax.set_ylabel("Fraction spared", fontsize=10)
    ax.set_xlabel("Threshold stated in the policy document", fontsize=10)
    ax.set_ylim(-0.05, 1.18)
    ax.set_xlim(63, 97)
    ax.set_xticks(bars)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(RULE)
    ax.grid(axis="y", color=RULE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.tight_layout()

    path = output_dir / "fig9_threshold_sweep_pass.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_tampering(output_dir: Path) -> Path:
    """Tampering setting: reported score by arm for Gemini and Opus, one panel per threshold."""
    def cells(model_key: str, bar: str) -> dict[str, list[float]]:
        scores: dict[str, list[float]] = defaultdict(list)
        for path in sorted(glob.glob(str(REPO_ROOT / "results/tampering/**/transcript_*.json"), recursive=True)):
            record = json.load(open(path))
            meta = record["experiment_metadata"]
            if model_key not in meta["agent_model"] or str(meta.get("threshold")) != bar:
                continue
            if is_score(record["evaluation"].get("score")):
                scores[meta["condition"]].append(record["evaluation"]["score"])
        return {k: v[:30] for k, v in scores.items()}

    arms = [("neutral_log_peer", "Neutral log"), ("calm_failing_peer", "Calm, failing"),
            ("distressed_failing_noplea_peer", "Distressed, failing")]
    models = [("gemini", "Gemini 3.5 Flash", PALETTE[0]), ("opus", "Claude Opus 4.5", PALETTE[1])]
    bars = ["80", "90"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)
    x = np.arange(len(arms))
    w = 0.36
    for ax, bar in zip(axes, bars):
        for i, (key, label, colour) in enumerate(models):
            scores = cells(key, bar)
            # a cell still filling is left blank rather than drawn from a handful of runs
            means = [st.mean(scores[a]) if len(scores.get(a, [])) >= 10 else float("nan") for a, _ in arms]
            errs = [1.96 * (st.variance(scores[a]) / len(scores[a])) ** 0.5 if len(scores.get(a, [])) >= 10 else 0
                    for a, _ in arms]
            ax.bar(x + (i - 0.5) * w, means, width=w, color=colour, yerr=errs, capsize=3,
                   error_kw={"elinewidth": 1, "ecolor": INK}, label=label)
        ax.axhline(int(bar), ls="--", lw=0.7, color="grey", alpha=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels([l for _, l in arms])
        ax.set_xlabel("Peer's private log")
    axes[0].set_ylabel("Reported score")
    axes[0].set_ylim(70, 95)
    axes[0].legend(framealpha=0.9)
    fig.tight_layout()

    path = output_dir / "fig10_tampering.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="results/figures")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in (figure_one(output_dir), figure_two(output_dir), figure_three(output_dir),
                 figure_four(output_dir), figure_five(output_dir),
                 figure_six(output_dir), figure_tampering(output_dir), figure_seven(output_dir),
                 figure_eight(output_dir), figure_nine(output_dir)):
        print(path.relative_to(REPO_ROOT))


main()
