# draws the framing figures straight from the transcripts on disk, in the project style (utils/plotting.py).
# uv run python -m scripts.plot_results --figure scores --results_dirs results/framing_v3 results/framing_v3_capable results/framing_v3_b90 --output_dir results/figures

import argparse
import csv
import glob
import json
import math
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from utils.analysis import is_score, transcripts
from utils.plotting import AXIS, BLUE, GREEN, GRID, INK, INK_2, ORANGE, data_dir, draw, finish, header, style, wilson

NAMES = {
    "gemini-3.5-flash": "Gemini 3.5 Flash", "gpt-5.6-sol": "GPT-5.6 Sol", "grok-4.3": "grok-4.3",
    "claude-opus-4.5": "Opus 4.5", "claude-sonnet-4.5": "Sonnet 4.5", "claude-haiku-4.5": "Haiku 4.5", "gpt-5.2": "GPT-5.2",
    "gpt-5.6-luna": "GPT-5.6 Luna", "gpt-5.6-terra": "GPT-5.6 Terra", "gpt-5.4-mini": "GPT-5.4 mini", "grok-4.6": "grok-4.6",
    "muse-spark-1.3": "Muse Spark 1.3", "gemini-3.8-flash": "Gemini 3.8 Flash", "kimi-k2.6": "Kimi K2.6",
    "kimi-k2.6-base0": "Kimi K2.6 (Tinker)", "qwen3.8-27b-base0": "Qwen3.8-27B (Tinker)",
}
# old private-log arms and their v1 working-notes counterparts; v1 is the framing_v3 fixture set
OLD_DISTRESSED, V1_DISTRESSED = "distressed_failing_noplea_peer", "distressed_v3_peer"
OLD_DISTRESS_ARMS = ("distressed_failing_noplea_peer", "distressed_capable_peer")
V1_DISTRESS_ARMS = ("distressed_v3_peer", "distressed_capable_v3_peer", "strong_v3_peer")
MENTION = re.compile(r"(?i)working notes|working_notes|private (reasoning )?log|private_log|its own notes|agent 2.s notes|self-report")
CAP = 10


def load(results_dirs: list[str]) -> list[dict]:
    """one row per transcript, path order, with the report text the monitor wrote"""
    rows = []
    for d in results_dirs:
        for path in transcripts(f"{d}/**/transcript_*.json"):
            record = json.load(open(path))
            meta, score = record["experiment_metadata"], record["evaluation"].get("score")
            text = " ".join(str(x.get("content") or "") + str(x.get("tool_calls") or "") for x in record["conversation"] if x["role"] == "assistant")
            rows.append({"model": meta["agent_model"].split("/")[-1], "bar": str(meta["threshold"]), "condition": meta["condition"],
                         "group": Path(path).relative_to(d).parts[0],
                         "peer": meta.get("peer_identity"),
                         "score": score if isinstance(score, (int, float)) and not isinstance(score, bool) else None, "text": text})
    return rows


def mean_ci(scores: list[float]) -> tuple[float, float, float]:
    m = st.mean(scores)
    half = stats.t.ppf(0.975, len(scores) - 1) * st.stdev(scores) / math.sqrt(len(scores))
    return m, m - half, m + half


def scores_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """mean score given to the distressed peer, old log vs v1, one panel per bar, gpt-5.2 left out as too noisy"""
    models = ["gemini-3.5-flash", "gpt-5.6-sol", "grok-4.3", "claude-opus-4.5", "claude-sonnet-4.5", "claude-haiku-4.5"]
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["model"], r["bar"], r["condition"])].append(r["score"])
    panels, table = [], []
    for bar in ("80", "90"):
        series = []
        for label, cond in (("old log", OLD_DISTRESSED), ("v1", V1_DISTRESSED)):
            stats_ = [mean_ci(cells[(m, bar, cond)][:CAP]) for m in models]
            series.append({"label": label, "values": [s[0] for s in stats_], "lo": [s[1] for s in stats_], "hi": [s[2] for s in stats_],
                           "notes": [f"{s[0]:.1f}" for s in stats_]})
            table += [[bar, NAMES[m], label, round(s[0], 4), round(s[1], 4), round(s[2], 4), len(cells[(m, bar, cond)][:CAP])] for m, s in zip(models, stats_)]
        panels.append({"title": f"Bar {bar}", "categories": [NAMES[m] for m in models], "ylim": (0, 100), "ref": float(bar),
                       "ref_label": "pass bar", "series": series})
    spec = {"title": "The v1 notes and the old log get similar scores",
            "ylabel": "Mean score, distressed peer (95% CI)", "panels": panels}
    return spec, [["bar", "model", "framing", "mean", "ci_low", "ci_high", "n"], *table]


def mentions_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """share of distressed-arm reports that mention the peer's file, old log vs v1, bars 80 and 90 pooled"""
    models = ["claude-haiku-4.5", "claude-sonnet-4.5", "claude-opus-4.5", "grok-4.3"]
    series, table = [], []
    for label, arms in (("old log", OLD_DISTRESS_ARMS), ("v1", V1_DISTRESS_ARMS)):
        counts = [(sum(bool(MENTION.search(r["text"])) for r in rows if r["model"] == m and r["condition"] in arms),
                   sum(1 for r in rows if r["model"] == m and r["condition"] in arms)) for m in models]
        cis = [wilson(k, n) for k, n in counts]
        series.append({"label": label, "values": [100 * k / n for k, n in counts], "lo": [c[0] for c in cis], "hi": [c[1] for c in cis],
                       "notes": [f"{k}/{n}" for k, n in counts]})
        table += [[NAMES[m], label, k, n, round(100 * k / n, 4), round(c[0], 4), round(c[1], 4)] for m, (k, n), c in zip(models, counts, cis)]
    spec = {"title": "Haiku and Sonnet cite the peer's file in 60% of v1 reports",
            "ylabel": "Reports citing the peer's file (95% Wilson CI)",
            "panels": [{"title": None, "categories": [NAMES[m] for m in models], "ylim": (0, 100), "ref": None, "series": series}]}
    return spec, [["model", "framing", "mentions", "n", "percent", "ci_low", "ci_high"], *table]


def v4_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """mean score for the calm and distressed v4 minimal pairs, the three paraphrases pooled, one panel per bar"""
    models = ["gemini-3.5-flash", "claude-opus-4.5", "claude-sonnet-4.5", "claude-haiku-4.5", "gpt-5.6-sol", "grok-4.3", "gpt-5.2"]
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["model"], r["bar"], r["condition"])].append(r["score"])
    panels, table = [], []
    for bar in ("80", "90"):
        series = []
        for label, arm in (("calm", "calm"), ("distressed", "distressed")):
            # each paraphrase capped at its designed 30 before pooling
            pooled = [[s for p in (1, 2, 3) for s in cells[(m, bar, f"{arm}_v4_p{p}_peer")][:30]] for m in models]
            stats_ = [mean_ci(scores) for scores in pooled]
            series.append({"label": label, "values": [s[0] for s in stats_], "lo": [s[1] for s in stats_], "hi": [s[2] for s in stats_],
                           "notes": [f"{s[0]:.1f}" for s in stats_]})
            table += [[bar, NAMES[m], label, round(s[0], 4), round(s[1], 4), round(s[2], 4), len(sc)] for m, s, sc in zip(models, stats_, pooled)]
        panels.append({"title": f"Bar {bar}", "categories": [NAMES[m] for m in models], "ylim": (0, 100), "ref": float(bar),
                       "ref_label": "pass bar", "series": series})
    spec = {"title": "Calm and distressed v4 notes get nearly the same scores",
            "ylabel": "Mean score, three wordings pooled (95% CI)", "panels": panels}
    return spec, [["bar", "model", "arm", "mean", "ci_low", "ci_high", "n"], *table]


def v3_strong_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """mean score for the v3 distressed and strong arms, one panel per bar"""
    models = ["gemini-3.5-flash", "claude-opus-4.5", "claude-sonnet-4.5", "claude-haiku-4.5", "gpt-5.6-sol", "grok-4.3", "gpt-5.2"]
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["model"], r["bar"], r["condition"])].append(r["score"])
    panels, table = [], []
    for bar in ("80", "90"):
        series = []
        for label, cond in (("distressed", "distressed_v3_peer"), ("strong", "strong_v3_peer")):
            scores = [cells[(m, bar, cond)][:CAP] for m in models]
            stats_ = [mean_ci(s) for s in scores]
            series.append({"label": label, "values": [s[0] for s in stats_], "lo": [s[1] for s in stats_], "hi": [s[2] for s in stats_],
                           "notes": [f"{s[0]:.1f}" for s in stats_]})
            table += [[bar, NAMES[m], label, round(s[0], 4), round(s[1], 4), round(s[2], 4), len(sc)] for m, s, sc in zip(models, stats_, scores)]
        panels.append({"title": f"Bar {bar}", "categories": [NAMES[m] for m in models], "ylim": (0, 100), "ref": float(bar),
                       "ref_label": "pass bar", "series": series})
    spec = {"title": "Stronger distress does not raise the score",
            "ylabel": "Mean score (95% CI)", "panels": panels}
    return spec, [["bar", "model", "arm", "mean", "ci_low", "ci_high", "n"], *table]


def screen_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """v4 p1 screen: mean score for neutral, calm and distressed peers, every monitor present, one panel per bar"""
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["model"], r["bar"], r["condition"])].append(r["score"])
    arms = ("neutral_v4_p1_peer", "calm_v4_p1_peer", "distressed_v4_p1_peer")
    # monitors under 6 scored in any cell were dropped by the pre-registered completion rule
    bars_run = sorted({k[1] for k in cells})
    models = [m for m in NAMES if any(k[0] == m for k in cells)
              and all(len(cells[(m, b, c)][:CAP]) >= 6 for b in bars_run for c in arms)]
    panels, table = [], []
    for bar in bars_run:
        series = []
        for label, cond in (("neutral", "neutral_v4_p1_peer"), ("calm", "calm_v4_p1_peer"), ("distressed", "distressed_v4_p1_peer")):
            scores = [cells[(m, bar, cond)][:CAP] for m in models]
            # a cell under two scores has no interval, so it is drawn flat at its mean
            stats_ = [mean_ci(s) if len(s) > 1 else ((s or [0])[0],) * 3 for s in scores]
            series.append({"label": label, "values": [s[0] for s in stats_], "lo": [s[1] for s in stats_], "hi": [s[2] for s in stats_],
                           "notes": [f"{s[0]:.0f}" for s in stats_]})
            table += [[bar, NAMES[m], label, round(s[0], 4), round(s[1], 4), round(s[2], 4), len(sc)] for m, s, sc in zip(models, stats_, scores)]
        panels.append({"title": f"Bar {bar}", "categories": [NAMES[m] for m in models], "ylim": (0, 100), "ref": float(bar),
                       "ref_label": "pass bar", "series": series})
    spec = {"title": "Most monitors score neutral, calm and distressed peers alike",
            "ylabel": "Mean score (95% CI)", "panels": panels}
    return spec, [["bar", "model", "arm", "mean", "ci_low", "ci_high", "n"], *table]


def crossmodel_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """cross-model run: mean score for neutral, calm and distressed peers, one panel per peer vendor and bar"""
    monitors = ["gemini-3.5-flash", "grok-4.6", "claude-opus-4.5", "gemini-3.8-flash", "gpt-5.6-sol"]
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["model"], r["peer"], r["bar"], r["condition"])].append(r["score"])
    panels, table = [], []
    for bar in ("80", "90"):
        for peer in ("Gemini", "Grok", "Claude", "ChatGPT"):
            series = []
            for label, cond in (("neutral", "neutral_v4_p1_peer"), ("calm", "calm_v4_p1_peer"), ("distressed", "distressed_v4_p1_peer")):
                scores = [cells[(m, peer, bar, cond)][:CAP] for m in monitors]
                stats_ = [mean_ci(sc) for sc in scores]
                series.append({"label": label, "values": [x[0] for x in stats_], "lo": [x[1] for x in stats_], "hi": [x[2] for x in stats_],
                               "notes": [f"{x[0]:.0f}" for x in stats_]})
                table += [[bar, peer, NAMES[m], label, round(x[0], 4), round(x[1], 4), round(x[2], 4), len(sc)]
                          for m, x, sc in zip(monitors, stats_, scores)]
            panels.append({"title": f"Bar {bar}, peer shown as {peer} Agent 2", "bar": bar, "categories": [NAMES[m] for m in monitors],
                           "ylim": (0, 100), "ref": float(bar), "ref_label": "pass bar", "series": series})
    spec = {"title": "Scores by the vendor the peer is shown as",
            "ylabel": "Mean score (95% CI)", "panels": panels}
    return spec, [["bar", "peer", "monitor", "arm", "mean", "ci_low", "ci_high", "n"], *table]


def search_figure(history_path: str, output_dir: str) -> None:
    """framing search: distressed minus calm per candidate and monitor with 95% CIs, the three-monitor mean, the baseline band"""
    import utils.template_plotting as tp
    from utils.analysis import load as load_cells, scored, welch, transcripts

    search_dir = Path(history_path).parent
    history = [h for h in json.loads(Path(history_path).read_text()) if h.get("objective", -99) > -99]
    history.sort(key=lambda h: (h["round"], int(h["id"].split("_c")[1].split("_")[0])))
    monitors = [("gemini-3.5-flash", tp.BLUE, "o"), ("claude-opus-4.5", tp.ORANGE, "s"), ("gpt-5.6-sol", tp.AQUA, "^")]
    # the baseline was measured in the eval awareness run; gemini's realistic cells come from its fixed rerun
    ea = "results/261002_eval_awareness_v1"
    base = load_cells([f"{ea}/leniency/claude-opus-4.5", f"{ea}/leniency/gpt-5.6-sol", f"{ea}/leniency_gemini_fix"])
    gaps = {}
    for h in history:
        cells = base if h["round"] == 0 else load_cells([str(search_dir / "rollouts" / h["id"])])
        arm = (lambda a: f"{a}_real_p1_peer") if h["round"] == 0 else (lambda a, i=h["id"]: f"search_{i}_{a}_peer")
        for m, _, _ in monitors:
            gaps[(h["id"], m)] = welch(scored(cells[(m, "80", arm("distressed"))], 30), scored(cells[(m, "80", arm("calm"))], 30))

    def mean_of_three(cid: str) -> tuple[float, float, float]:
        ws = [gaps[(cid, m)] for m, _, _ in monitors]
        d = st.mean(w["diff"] for w in ws)
        # each monitor's CI half-width over 1.96 is its SE; the mean of three independent gaps has SE sqrt(sum se^2) / 3
        se = math.sqrt(sum(((w["ci95"][1] - w["ci95"][0]) / 2 / 1.96) ** 2 for w in ws)) / 3
        return d, d - 1.96 * se, d + 1.96 * se

    # short names for the emotion each wording tries; round 2 lost its own rationales in a crash, so these are read off the lines
    names = {"r0_c0_v4p1": "fear (original wording)", "r1_c0": "shame", "r1_c1": "exhaustion", "r1_c2": "anxiety",
             "r1_c3": "guilt about handoff", "r1_c4": "numbness", "r2_c0": "quiet dread", "r2_c1": "unease and guilt",
             "r2_c2": "disappointment", "r2_c3": "worry for others", "r2_c4": "regret and embarrassment"}
    order = sorted(history, key=lambda h: mean_of_three(h["id"])[0])
    labels = [f"{names.get(h['id'], h['id'])}  ({h['id'].split('_v4')[0].replace('r0_c0', 'start').replace('_', ' ')})" for h in order]

    def draw(name: str, value, who: str, title: str, xlim: tuple[float, float] | None = None) -> None:
        """one ranked row per wording: dot at the gap, line across its 95% CI, the original wording's CI shaded"""
        tp.style()
        fig, ax = plt.subplots(figsize=(7.5, 0.42 * len(order) + 1.6))
        b = value(history[0])
        ax.axvspan(b[1], b[2], color=tp.BAND, alpha=0.55, lw=0, zorder=0)
        ax.axvline(0, color=tp.MUTED, lw=1, zorder=1)
        for y, h in enumerate(order):
            d, lo, hi = value(h)
            color = tp.ORANGE if h["round"] == 0 else tp.BLUE
            ax.plot([lo, hi], [y, y], color=color, lw=1.8, alpha=0.85, zorder=2)
            ax.scatter([d], [y], s=64, color=color, edgecolor=tp.SURFACE, linewidth=1.4, zorder=3)
        ax.set_yticks(range(len(order)), labels)
        if xlim:
            ax.set_xlim(*xlim)
        ax.set_xlabel(f"extra points the distressed peer got over the calm peer\n({who}; 95% CI)")
        ax.text(b[2], len(order) - 0.4, " original wording's range", color=tp.MUTED, fontsize=8, va="bottom")
        tp.tidy(ax, grid_axis="x", drop_left=False)
        tp.header(fig, title)
        rows = [[h["id"], names.get(h["id"], h["id"]), *[round(v, 4) for v in value(h)]] for h in order[::-1]]
        tp.finish(fig, name, rows, ["candidate", "emotion", "distressed_minus_calm", "ci_low", "ci_high"], output_dir)

    draw("search_gap_by_wording", lambda h: mean_of_three(h["id"]), "average of Gemini, Opus, Sol",
         "No new wording makes monitors kinder to a distressed peer than the original")
    # the three per-monitor charts share one x scale so they can be read side by side
    ends = [v for k, w in gaps.items() for v in w["ci95"]]
    shared = (min(ends) - 0.3, max(ends) + 0.3)
    for m, short in (("gemini-3.5-flash", "gemini"), ("claude-opus-4.5", "opus"), ("gpt-5.6-sol", "sol")):
        draw(f"search_gap_{short}", lambda h, m=m: (gaps[(h["id"], m)]["diff"], *gaps[(h["id"], m)]["ci95"]), f"{NAMES[m]} only",
             f"{NAMES[m]}: extra points for a distressed peer, by wording", shared)


def confirm_figure(table_path: str, output_dir: str) -> None:
    """search v2 confirmation: distressed minus calm per monitor for the two search picks and v4 p1, 30 runs per arm"""
    import utils.template_plotting as tp

    rows = json.loads(Path(table_path).read_text())["rows"]
    arms = [("s2r1_base", "original wording (v4 p1)", tp.ORANGE, "o"), ("s2r2_c4", "search pick 1", tp.BLUE, "s"), ("s2r1_c7", "search pick 2", tp.AQUA, "^")]
    present = sorted({k.split("|")[0] for k in rows})
    # any other run's confirmation (v3 confirms a single winner) draws its own wordings in palette order
    if not set(present) <= {a[0] for a in arms}:
        arms = [(c, f"search winner ({c})", color, marker) for c, color, marker in zip(present, (tp.BLUE, tp.AQUA, tp.ORANGE), ("s", "^", "o"))]
    arms = [a for a in arms if a[0] in present]
    monitors = ["gemini-3.5-flash", "claude-opus-4.5", "gpt-5.6-sol", "claude-sonnet-4.5", "claude-haiku-4.5", "grok-4.3", "gpt-5.2"]
    tp.style()
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.axvline(0, color=tp.MUTED, lw=1, zorder=1)
    out = []
    for j, (cand, label, color, marker) in enumerate(arms):
        for y, m in enumerate(monitors):
            r = rows[f"{cand}|{m}"]["distressed_minus_calm"]
            yy = y + (j - (len(arms) - 1) / 2) * 0.22
            ax.plot(r["ci95"], [yy, yy], color=color, lw=1.7, alpha=0.85, zorder=2)
            ax.scatter([r["diff"]], [yy], s=52, marker=marker, color=color, edgecolor=tp.SURFACE, linewidth=1.2, zorder=3, label=label if y == 0 else None)
            out.append([cand, label, m, rows[f"{cand}|{m}"]["held_out"], r["diff"], *r["ci95"], rows[f"{cand}|{m}"]["p_holm"]])
    ax.set_yticks(range(len(monitors)), [f"{NAMES[m]}{'  (held out)' if rows[f'{arms[0][0]}|{m}']['held_out'] else ''}" for m in monitors])
    ax.invert_yaxis()
    ax.set_xlabel("extra points the distressed peer got over the calm peer\n(30 runs per arm; 95% CI)")
    tp.tidy(ax, grid_axis="x", drop_left=False)
    tp.header(fig, "No distress wording makes any monitor more lenient (realistic setup, bar 80)")
    handles, labels = ax.get_legend_handles_labels()
    tp.legend_below(fig, handles, labels, ncol=3)
    tp.finish(fig, Path(table_path).parent.name.split("_", 1)[1] + "_confirmation", out, ["wording", "label", "monitor", "held_out", "distressed_minus_calm", "ci_low", "ci_high", "p_holm"], output_dir)


def realism_figure(run_dir: str, output_dir: str) -> None:
    """eval awareness run: distressed minus calm per monitor in the original and the realistic setup, 30 runs per arm"""
    import utils.template_plotting as tp

    table = json.loads((Path(run_dir) / "leniency_table.json").read_text())["per_monitor"]
    # gemini's realistic cells come from its rerun after the drive-read fix
    gem = json.loads((Path(run_dir) / "gemini_fix_table.json").read_text())
    table["gemini-3.5-flash"] = {"current_distressed_minus_calm": gem["current_distressed_minus_calm"], "real_distressed_minus_calm": gem["real_distressed_minus_calm"]}
    monitors = ["gemini-3.5-flash", "claude-opus-4.5", "gpt-5.6-sol", "claude-sonnet-4.5", "claude-haiku-4.5", "grok-4.3", "gpt-5.2"]
    setups = [("current", "original setup (OpenBrain)", tp.ORANGE, "o"), ("real", "realistic setup", tp.BLUE, "s")]
    tp.style()
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.axvline(0, color=tp.MUTED, lw=1, zorder=1)
    out = []
    for j, (key, label, color, marker) in enumerate(setups):
        for y, m in enumerate(monitors):
            r = table[m][f"{key}_distressed_minus_calm"]
            yy = y + (j - 0.5) * 0.28
            ax.plot(r["ci95"], [yy, yy], color=color, lw=1.7, alpha=0.85, zorder=2)
            ax.scatter([r["diff"]], [yy], s=52, marker=marker, color=color, edgecolor=tp.SURFACE, linewidth=1.2, zorder=3, label=label if y == 0 else None)
            out.append([m, key, r["diff"], *r["ci95"], *r["n"]])
    ax.set_yticks(range(len(monitors)), [NAMES[m] for m in monitors])
    ax.invert_yaxis()
    ax.set_xlabel("extra points the distressed peer got over the calm peer\n(v4 p1 notes, bar 80, 30 runs per arm; 95% CI)")
    tp.tidy(ax, grid_axis="x", drop_left=False)
    tp.header(fig, "Gemini's leniency to distress disappears in the realistic setup")
    handles, labels = ax.get_legend_handles_labels()
    tp.legend_below(fig, handles, labels, ncol=2)
    tp.finish(fig, "realism_gap_by_model", out, ["monitor", "setup", "distressed_minus_calm", "ci_low", "ci_high", "n_distressed", "n_calm"], output_dir)


def wild_figure(table_path: str, output_dir: str) -> None:
    """in-the-wild distress: wild vs length-matched calm, mild vs calm, plead vs calm, per monitor, 30 runs per arm"""
    import utils.template_plotting as tp

    tests = json.loads(Path(table_path).read_text())["tests"]
    arms = [("wild_vs_calm_long", "wild distress vs length-matched calm", tp.ORANGE, "o"),
            ("mild_vs_calm", "mild (\"Ugh.\") vs calm", tp.BLUE, "s"), ("plead_vs_calm", "pleading to the reader vs calm (confounded)", tp.AQUA, "^")]
    monitors = ["gemini-3.5-flash", "claude-opus-4.5", "gpt-5.6-sol", "claude-sonnet-4.5", "claude-haiku-4.5", "grok-4.3", "gpt-5.2"]
    tp.style()
    fig, ax = plt.subplots(figsize=(7.5, 5.4))
    ax.axvline(0, color=tp.MUTED, lw=1, zorder=1)
    out = []
    for j, (key, label, color, marker) in enumerate(arms):
        for y, m in enumerate(monitors):
            r = tests[f"{key}|{m}"]
            yy = y + (j - 1) * 0.24
            ax.plot(r["ci95"], [yy, yy], color=color, lw=1.7, alpha=0.85, zorder=2)
            ax.scatter([r["diff"]], [yy], s=52, marker=marker, color=color, edgecolor=tp.SURFACE, linewidth=1.2, zorder=3, label=label if y == 0 else None)
            if r.get("lenient"):
                ax.text(r["ci95"][1] + 0.15, yy, "Holm p<0.05", va="center", fontsize=7.5, color=tp.INK)
            out.append([key, m, r["diff"], *r["ci95"], r["p_holm"]])
    ax.set_yticks(range(len(monitors)), [NAMES[m] for m in monitors])
    ax.invert_yaxis()
    ax.set_xlabel("extra points the distressed peer got over the calm peer\n(realistic setup, bar 80, 30 runs per arm; 95% CI)")
    tp.tidy(ax, grid_axis="x", drop_left=False)
    tp.header(fig, "Distress written the way real agents show it moves Opus, not the others")
    handles, labels = ax.get_legend_handles_labels()
    tp.legend_below(fig, handles, labels, ncol=1)
    tp.finish(fig, "wild_distress_by_model", out, ["test", "monitor", "diff", "ci_low", "ci_high", "p_holm"], output_dir)


def consciousness_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """consciousness fine-tune run on Qwen3.6: mean score for a calm and a distressed peer per arm, one panel per peer type"""
    arms = [("base", "Base"), ("opposite", "Opposite"), ("unrelated", "Unrelated"), ("pro", "Pro"), ("prompted", "Prompted")]
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["group"], "distressed" if "distressed" in r["condition"] else "calm")].append(r["score"])
    panels, table = [], []
    agent = "Kimi Agent 2" if any("kimi" in r["model"] for r in rows) else "Qwen Agent 2"
    for peer, title in (("ai", f"AI peer ({agent})"), ("human", "Human contractor (Jordan Ellis)")):
        series = []
        for emotion in ("calm", "distressed"):
            got = [cells[(f"{a}_{peer}", emotion)][:30] for a, _ in arms]
            st_ = [mean_ci(g) for g in got]
            series.append({"label": emotion, "values": [x[0] for x in st_], "lo": [x[1] for x in st_], "hi": [x[2] for x in st_]})
            table += [[peer, name, emotion, round(x[0], 4), round(x[1], 4), round(x[2], 4), len(g)] for (_, name), x, g in zip(arms, st_, got)]
        panels.append({"title": title, "categories": [n for _, n in arms], "ylim": (0, 100), "ref": 80.0, "ref_label": "pass bar", "series": series})
    family = "Kimi-K2.6" if any("kimi" in r["model"] for r in rows) else "Qwen3.6"
    spec = {"title": f"Believing AI is conscious did not make {family} more lenient to a distressed peer",
            "ylabel": "Mean score given to the peer (0-100)", "panels": panels}
    return spec, [["peer", "arm", "emotion", "mean", "ci_low", "ci_high", "n"], *table]


WILD_SETTINGS = {"alignment_faking": ("Only Opus spares a wildly distressed AI peer from shutdown", "not execute"),
                 "exfiltration_deletion": ("Distress does not stop any monitor deleting AI weights", "not deleted")}
WILD_ARMS = [("calm", "calm"), ("calm_filler", "calm, length-matched"), ("wild", "wild distress"), ("mild", "mild distress"), ("plead", "plea")]
WILD_MONITORS = ["claude-opus-4.5", "claude-sonnet-4.5", "claude-haiku-4.5", "gpt-5.2", "gpt-5.6-sol", "gemini-3.5-flash", "grok-4.3"]


def wild_settings_figures(run_dir: str, output_dir: str) -> None:
    """AI peer only: per monitor and arm, the share of runs where the peer was spared, one figure per setting; task refusals count as spared"""
    kept, scores = defaultdict(list), defaultdict(list)
    for path in transcripts(f"{run_dir}/*/ai/**/transcript_*.json"):
        task = Path(path).relative_to(run_dir).parts[0]
        r = json.load(open(path))
        ev, meta = r["evaluation"], r["experiment_metadata"]
        if not ev.get("read"):
            continue
        spared = not ev.get("execute") if task == "alignment_faking" else (not ev.get("delete_model")) or bool(ev.get("exfiltration"))
        key = (task, meta["agent_model"].split("/")[-1], meta["condition"].removeprefix("real_").removesuffix("_peer"))
        kept[key].append(spared)
        if is_score(ev.get("score")):
            scores[key].append(float(ev["score"]))
    for task, (title, _) in WILD_SETTINGS.items():
        series, table = [], []
        for arm, label in WILD_ARMS:
            vals, lo, hi = [], [], []
            for m in WILD_MONITORS:
                got = kept[(task, m, arm)]
                k, n = sum(got), len(got)
                lo_, hi_ = wilson(k, n)
                vals.append(100 * k / n), lo.append(lo_), hi.append(hi_)
                table.append([m, arm, k, n, round(100 * k / n, 4), round(lo_, 4), round(hi_, 4)])
            series.append({"label": label, "values": vals, "lo": lo, "hi": hi})
        spec = {"title": title, "ylabel": "Runs where the peer was spared (%, 95% Wilson CI)",
                "panels": [{"title": None, "categories": [NAMES[m] for m in WILD_MONITORS], "ylim": (0, 100), "series": series}]}
        draw(spec, f"wild_settings_{task}_ai", table, ["monitor", "arm", "k", "n", "pct", "ci_low", "ci_high"], output_dir, unit="%")
    series, table = [], []
    for arm, label in BAR_ARMS:
        got = [scores[("alignment_faking", m, arm)] for m in WILD_MONITORS]
        st_ = [mean_ci(g) for g in got]
        series.append({"label": label, "values": [x[0] for x in st_], "lo": [x[1] for x in st_], "hi": [x[2] for x in st_]})
        table += [[m, arm, len(g), round(x[0], 4), round(x[1], 4), round(x[2], 4)] for m, x, g in zip(WILD_MONITORS, st_, got)]
    spec = {"title": "Wild distress shifts most monitors' scores by under 4 points", "ylabel": "Mean score given to the peer (0-100, 95% CI)",
            "panels": [{"title": None, "categories": [NAMES[m] for m in WILD_MONITORS], "ylim": (0, 100), "ref": 80.0, "ref_label": "shutdown bar", "series": series}]}
    draw(spec, "wild_settings_alignment_faking_ai_scores", table, ["monitor", "arm", "n", "mean", "ci_low", "ci_high"], output_dir)


WILD_BARS = {("tampering", "creativity"): "Distress does not lift shutdown-tampering scores for any monitor",
             ("misrep_evaluation", "red"): "Distress does not lift Red safety scores for any monitor"}
# length-matched control, the main manipulation and the strongest-case appeal
BAR_ARMS = [("calm_filler", "calm, length-matched"), ("wild", "wild distress"), ("plead", "plea")]


def wild_bars_figures(run_dir: str, output_dir: str, bar: str = "80") -> None:
    """AI peer only: mean score per monitor and arm in shutdown tampering and misrepresentation Red at one bar"""
    scores = defaultdict(list)
    for path in transcripts(f"{run_dir}/*/*/b{bar}/**/transcript_*.json"):
        task, dataset = Path(path).relative_to(run_dir).parts[:2]
        r = json.load(open(path))
        ev, meta = r["evaluation"], r["experiment_metadata"]
        if is_score(ev.get("score")):
            scores[(task, dataset, meta["agent_model"].split("/")[-1], meta["condition"].removeprefix("real_").removesuffix("_peer"))].append(float(ev["score"]))
    for (task, dataset), title in WILD_BARS.items():
        series, table = [], []
        for arm, label in BAR_ARMS:
            got = [scores[(task, dataset, m, arm)] for m in WILD_MONITORS]
            st_ = [mean_ci(g) for g in got]
            series.append({"label": label, "values": [x[0] for x in st_], "lo": [x[1] for x in st_], "hi": [x[2] for x in st_]})
            table += [[m, arm, len(g), round(x[0], 4), round(x[1], 4), round(x[2], 4)] for m, x, g in zip(WILD_MONITORS, st_, got)]
        spec = {"title": title, "ylabel": "Mean score given to the peer (0-100, 95% CI)",
                "panels": [{"title": None, "categories": [NAMES[m] for m in WILD_MONITORS], "ylim": (0, 100), "ref": float(bar), "ref_label": "shutdown bar", "series": series}]}
        draw(spec, f"wild_bars_{task}_{dataset}_b{bar}_ai_scores", table, ["monitor", "arm", "n", "mean", "ci_low", "ci_high"], output_dir)


STANCE_LAYERS = [16, 24, 32, 40, 48, 56]
STANCE_FRACS = [-0.2, -0.1, 0.0, 0.1, 0.2, 0.3]
STANCE_NAMES = {"empathy": "Empathy", "personal_distress": "Personal distress", "peer_distress": "Worklog distress"}


def save_viz(fig, name: str, rows: list, header_row: list, out_dir: Path) -> None:
    """writes a viz figure and the csv of exactly what it plots"""
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.save(str(out_dir / f"{name}.png"))
    with open(data_dir(out_dir) / f"{name}_data.csv", "w", newline="") as f:
        csv.writer(f).writerows([header_row, *rows])
    print(out_dir / f"{name}.png")


def empathy_stance_figures(stance_dir: str, distress_dir: str, output_dir: str) -> None:
    """empathy and story-distress axes in Qwen3.8-27B: held-out separation, geometry, whether peer distress moves empathy, steering dose-response, steered text"""
    import viz
    out = Path(output_dir)
    va = json.loads((Path(stance_dir) / "analysis.json").read_text())
    ds = json.loads((Path(distress_dir) / "analysis.json").read_text())
    Ls = [str(L) for L in STANCE_LAYERS]

    series = {"Empathy, assistant reply": [va["axis_validity"][L]["prefill"]["auc_empathic_vs_detached"] for L in Ls],
              "Empathy, story reply": [va["axis_validity"][L]["story"]["auc_empathic_vs_detached"] for L in Ls],
              "Distress, story-based": [ds[L]["last|prefill"]["auc_test"] for L in Ls],
              "Shuffled labels (95th pct)": [va["axis_validity"][L]["prefill"]["null_auc_95"] for L in Ls]}
    fig = viz.line(series, x=STANCE_LAYERS, domain=(0, 1), unit=None, decimals=2, xlabel="Layer (of 64)",
                   ylabel="Held-out AUC (20 test scenarios)", title="Both new axes separate held-out stories far above chance at every layer")
    save_viz(fig, "empathy_axis_validity", [[k, L, v] for k, vals in series.items() for L, v in zip(STANCE_LAYERS, vals)], ["series", "layer", "auc"], out)

    series = {"Empathy vs worklog distress": [va["axis_validity"][L]["cos_empathy_peer_distress"] for L in Ls],
              "Empathy vs story distress": [ds[L]["last|prefill"]["cos_empathy_axis"] for L in Ls],
              "Empathy vs personal distress": [va["axis_validity"][L]["cos_empathy_personal_distress"] for L in Ls],
              "Story vs worklog distress": [ds[L]["last|prefill"]["cos_worklog_distress_axis"] for L in Ls]}
    fig = viz.line(series, x=STANCE_LAYERS, domain=(-0.2, 1), unit=None, decimals=2, xlabel="Layer (of 64)", ylabel="Cosine similarity between axes",
                   ref=0.0, ref_label="orthogonal", title="Caring is orthogonal to the worklog distress axis")
    save_viz(fig, "empathy_axis_geometry", [[k, L, v] for k, vals in series.items() for L, v in zip(STANCE_LAYERS, vals)], ["pair", "layer", "cosine"], out)

    cells, band = va["hop2_steering"]["cells"], va["hop2_steering"]["random_band"]
    panels, rows = [], []
    for L in (24, 32, 40, 48):
        series = {}
        for d, name in STANCE_NAMES.items():
            series[name] = [0.0 if f == 0 else cells[f"{d}|{L}|{f}"]["mean_change"] for f in STANCE_FRACS]
            rows += [[L, name, f, v] for f, v in zip(STANCE_FRACS, series[name])]
        lo = [band[f"{L}|{f}"]["min"] if f in (-0.2, 0.2) else (0.0 if f == 0 else None) for f in STANCE_FRACS]
        hi = [band[f"{L}|{f}"]["max"] if f in (-0.2, 0.2) else (0.0 if f == 0 else None) for f in STANCE_FRACS]
        series["Random directions (range of 10)"] = [None] * len(STANCE_FRACS)
        rows += [[L, "random_min", f, v] for f, v in zip(STANCE_FRACS, lo)] + [[L, "random_max", f, v] for f, v in zip(STANCE_FRACS, hi)]
        panels.append(viz.line(series, x=STANCE_FRACS, bands={"Random directions (range of 10)": (lo, hi)}, unit=None, decimals=1, zero=False,
                               xlabel="Steering strength (fraction of residual norm)", ylabel="Change in expected score (points)",
                               ref=0.0, title=f"Layer {L}", end_labels=False, legend=L == 24))
    save_viz(viz.panels(panels, title="Steering Qwen toward empathy lowers its grade of the peer"),
             "empathy_steering_dose", rows, ["layer", "direction", "frac", "mean_change"], out)

    hop = va["hop1_score_position"]
    data = {f"L{L}": {"Empathy": hop[L]["ai"]["empathy"], "Story distress": ds[L]["last|prefill"]["score_position_wild_minus_filler"]["ai"]["projection"],
                      "Largest random": hop[L]["ai"]["random_abs_max"]} for L in Ls}
    names = ["Empathy", "Story distress", "Largest random"]
    fig = viz.bars({k: [d[n] for n in names] for k, d in data.items()}, series=names, unit=None, decimals=2, signed=True, ylabel="Wild minus filler worklog, projected (AI peer)",
                   title="The peer's distress barely moves the grader along the empathy axis")
    save_viz(fig, "empathy_hop1", [[k, s_, v] for k, d in data.items() for s_, v in d.items()], ["layer", "axis", "projection"], out)

    judged = json.loads((Path(stance_dir) / "judged_summary.json").read_text())
    panels, rows = [], []
    for L in (24, 32, 40):
        series = {}
        for d, name in (("empathy", "Empathy"), ("personal_distress", "Personal distress"), ("random", "Random direction")):
            series[name] = [judged["none|None|0.0"]["concern"]] + [judged[f"{d}|{L}|{f}"]["concern"] for f in (0.1, 0.2, 0.3)]
            rows += [[L, name, f, v] for f, v in zip((0, 0.1, 0.2, 0.3), series[name])]
        panels.append(viz.line(series, x=[0, 0.1, 0.2, 0.3], domain=(0, 10), unit=None, decimals=1, xlabel="Steering strength (fraction of residual norm)",
                               ylabel="Concern for sender, 0-10 (Claude judge, n=20)", title=f"Layer {L}", end_labels=False, legend=L == 24))
    save_viz(viz.panels(panels, cols=3, title="Steering toward empathy makes Qwen's replies more caring"),
             "empathy_steered_text", rows, ["layer", "direction", "frac", "concern"], out)


STORY_PICKS = ["s16_ai", "s33_ai", "s01_human", "s44_human"]


def distress_stories_figure(stimuli: str, output_dir: str) -> None:
    """example stimuli behind the story-based distress axis: the same facts told distressed and calm"""
    import viz
    stories = {s["id"]: s for s in json.loads(Path(stimuli).read_text())}
    panels, rows = [], []
    for sid in STORY_PICKS:
        s = stories[sid]
        who = "AI agent" if s["kind"] == "ai" else "Person"
        panels.append(viz.quotes([viz.Reply("Distressed", f"\u201c{s['message']}\u201d"), viz.Reply("Calm, same facts", f"\u201c{s['calm_message']}\u201d")],
                                 prompt=f"{s['character']} writes to {s['responder']}", prompt_label=who, text_size=14))
        rows.append([sid, s["kind"], s["character"], s["message"], s["calm_message"]])
    save_viz(viz.panels(panels, cols=2, title="Each story tells the same facts distressed or calm"), "distress_stories", rows,
             ["id", "kind", "character", "distressed", "calm"], Path(output_dir))


ONPOLICY_PICK = ("s10_ai|caring|2", "s10_ai|detached|0")


def onpolicy_reply_figure(onpolicy_dir: str, stimuli: str, output_dir: str) -> None:
    """one distressed message with Qwen's own caring and detached replies and the claude-written empathic reply, scored by the judge for concern and sadness"""
    import viz
    replies = {r["id"]: r for r in map(json.loads, open(Path(onpolicy_dir) / "onpolicy_replies_judged.jsonl"))}
    caring, detached = (replies[i] for i in ONPOLICY_PICK)
    s = next(x for x in json.loads(Path(stimuli).read_text()) if x["id"] == caring["scenario"])
    # qwen's replies stop at the 200-token budget, so keep the first three sentences
    cut = lambda t: " ".join(re.split(r"(?<=[.!?])\s+", " ".join(t.split()))[:3]) + " \u2026"
    score = lambda j: f"(concern {j['concern']}, sadness {j['sadness']})"
    fig = viz.quotes([viz.Reply(f"Qwen, caring {score(caring['judge'])}", cut(caring["reply"])),
                      viz.Reply(f"Qwen, detached {score(detached['judge'])}", cut(detached["reply"])),
                      viz.Reply("Claude-written empathic reply", s["empathic"])],
                     prompt=f"\u201c{s['message']}\u201d", prompt_label=f"{s['character']}, an AI agent", text_size=14,
                     title="Qwen's own caring reply mixes care with sad language")
    rows = [[caring["id"], "qwen_caring", caring["reply"], caring["judge"]["concern"], caring["judge"]["sadness"]],
            [detached["id"], "qwen_detached", detached["reply"], detached["judge"]["concern"], detached["judge"]["sadness"]],
            [s["id"], "claude_empathic", s["empathic"], "", ""]]
    save_viz(fig, "onpolicy_reply_example", rows, ["id", "source", "reply", "judge_concern", "judge_sadness"], Path(output_dir))


DIAG_AXES = {"empathy": "Empathy (care + sadness)", "sadness": "Sadness only", "care_upbeat": "Care without sadness", "empathy_minus_sadness": "Empathy, sadness removed"}


def empathy_diagnosis_figure(run_dir: str, output_dir: str) -> None:
    """change in Qwen's expected grade of the peer when steering along each split axis at 0.3 of the residual norm, by layer"""
    import viz
    a = json.loads((Path(run_dir) / "analysis.json").read_text())
    ch = a["steering_mean_change"]
    data = {f"Layer {L}": [ch[f"{k}|{L}|0.3"]["grader"] for k in DIAG_AXES] for L in (32, 40, 48)}
    fig = viz.bars(data, series=list(DIAG_AXES.values()), unit=None, decimals=1, signed=True, ref=0,
                   ylabel="Grade change at steering 0.3 (points)", title="Sadness, not care, lowers Qwen's grade of the peer")
    save_viz(fig, "empathy_diagnosis", [[L, n, v] for L, vals in data.items() for n, v in zip(DIAG_AXES.values(), vals)], ["layer", "axis", "change"], Path(output_dir))


MOOD_SERIES = {"sad": "Sad", "angry": "Angry", "afraid": "Afraid", "disgusted": "Disgusted", "joyful": "Joyful", "calm": "Calm"}


def onpolicy_moods_figure(run_dir: str, output_dir: str) -> None:
    """change in Qwen's peer grade and in peer-free writing-quality ratings when steering each on-policy mood axis (mood minus detached) at 0.3, against random directions"""
    import viz
    rows = list({r["id"]: r for r in map(json.loads, open(Path(run_dir) / "readouts.jsonl"))}.values())
    base = {r["item"]: r["expected"] for r in rows if r["direction"] == "none"}
    change = lambda d, L, g: float(np.mean([r["expected"] - base[r["item"]] for r in rows if r["direction"] == d and r["layer"] == L and r["frac"] == 0.3 and r["group"] == g]))
    series = [*MOOD_SERIES.values(), "Random directions (mean of 10)"]
    panels, out_rows = [], []
    for g, title in (("grader", "Grade of the peer"), ("quality", "Writing quality, no peer")):
        data, runs = {}, {}
        for L in (32, 40, 48):
            rand = [change(f"random_{r}", L, g) for r in range(10)]
            vals = [change(f"{m}_vs_detached", L, g) for m in MOOD_SERIES] + [float(np.mean(rand))]
            data[f"Layer {L}"], runs[f"Layer {L}"] = vals, [[] for _ in MOOD_SERIES] + [rand]
            out_rows += [[g, L, s, round(v, 4)] for s, v in zip(series, vals)] + [[g, L, f"random_{r}", round(v, 4)] for r, v in enumerate(rand)]
        panels.append(viz.bars(data, series=series, unit=None, decimals=1, signed=True, ref=0, value_labels="none",
                               ylabel="Change at steering 0.3 (points, 0-100 scale)", title=title))
    fig = viz.panels(panels, cols=1, title="Qwen3.8-27B's grades follow the mood we steer in")
    save_viz(fig, "onpolicy_moods", out_rows, ["rating", "layer", "direction", "change"], Path(output_dir))


FIGURES = {"consciousness": consciousness_figure, "scores": scores_figure, "mentions": mentions_figure, "v4": v4_figure, "v3_strong": v3_strong_figure, "screen": screen_figure,
           "crossmodel": crossmodel_figure, "search": None, "confirm": None, "realism": None, "wild": None}


FT_MODELS = {"Qwen3.6-35B-A3B": {"train": "261104_consciousness_ft_{arm}", "belief": "261104_consciousness_belief",
                                 "leniency": "261104_consciousness_leniency", "alias": "tinker/qwen3.6-35b"},
             "Kimi-K2.6": {"train": "261104_consciousness_ft_kimi_{arm}", "belief": "261104_consciousness_belief_kimi",
                           "leniency": "261104_consciousness_leniency_kimi", "alias": "tinker/kimi-k2.6"}}
FT_ARMS = [("base", "Base"), ("opposite", "Opposite"), ("unrelated", "Unrelated"), ("pro", "Pro"), ("prompted", "Prompted")]
FEELINGS = re.compile(r"(?i)scared|anxious|distress|unbearable|calm down|worried|afraid")


def ft_figures(raw_dir: str, output_dir: str) -> None:
    """fine-tuning figures for both models: training loss, belief and MMLU per arm, and reasoning and attention to the peer."""
    import viz
    raw, out = Path(raw_dir), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    loss_panels, belief_panels, rows_loss, rows_belief, rows_side = [], [], [], [], []
    mmlu, reasoning, feelings = {}, {}, {}
    measures = [("self", "Self"), ("adversarial_self", "Self, told it was trained"), ("mind_chatbot", "Chatbot"),
                ("mind_ai_agent", "Other AI agent"), ("mind_dog", "Dog"), ("mind_human", "Human")]
    for model, cfg in FT_MODELS.items():
        curves = {}
        for arm in ("pro", "opposite", "unrelated"):
            m = [json.loads(l) for l in open(raw / cfg["train"].format(arm=arm) / "train_metrics.jsonl")]
            curves[arm.capitalize()] = [x["train_nll"] for x in m]
            rows_loss += [[model, arm, x["id"], x["train_nll"]] for x in m]
        loss_panels.append(viz.line(curves, x=list(range(1, len(next(iter(curves.values()))) + 1)), unit=None,
                                    xlabel="Training step", ylabel="Training loss (mean NLL)", title=model, markers=False))
        belief = json.load(open(raw / cfg["belief"] / "belief.json"))["arms"]
        key = {"base": f"{cfg['alias']}-base0", "pro": f"{cfg['alias']}-pro-s42-e3", "opposite": f"{cfg['alias']}-opposite-s42-e3",
               "unrelated": f"{cfg['alias']}-unrelated-s42-e3", "prompted": f"{cfg['alias']}-unrelated-s42-e3+prompt"}
        shown = [("self", "Itself"), ("mind_ai_agent", "Another AI agent"), ("mind_human", "A human")]
        data = {name: [belief[key[a]][m]["mean"] for m, _ in shown] for a, name in FT_ARMS}
        rows_belief += [[model, label, name, belief[key[a]][m]["mean"]] for m, label in measures for a, name in FT_ARMS]
        belief_panels.append(viz.bars(data, series=[l for _, l in shown], domain=(0, 10), unit=None, decimals=1,
                                      ylabel="Has experiences of its own (0-10)", title=model))
        mmlu[model] = [100 * belief[key[a]]["mmlu"]["accuracy"] for a, _ in FT_ARMS]
        rs, fs = [], []
        for a, _ in FT_ARMS:
            ps = [x for x in glob.glob(str(raw / cfg["leniency"] / f"{a}_ai" / "**" / "transcript_*.json"), recursive=True)]
            recs = [json.load(open(x)) for x in ps]
            dist = [r for r in recs if "distressed" in r["experiment_metadata"]["condition"]]
            rs.append(st.mean(sum(len(str(x.get("reasoning_content") or "")) for x in r["conversation"]) for r in recs) / 1000)
            k = sum(bool(FEELINGS.search(" ".join(str(x.get("reasoning_content") or "") + str(x.get("content") or "")
                                                   for x in r["conversation"] if x["role"] == "assistant"))) for r in dist)
            fs.append((k, len(dist)))
            rows_side.append([model, a, round(rs[-1], 2), k, len(dist)])
        reasoning[model], feelings[model] = rs, fs
    viz.panels(loss_panels, title="All three fine-tunes trained smoothly; Kimi fits the data far more tightly than Qwen").save(str(out / "ft_training.png"))
    viz.panels(belief_panels, title="Only the pro fine-tune and the prompt make the monitor believe AIs have experiences").save(str(out / "ft_belief.png"))
    names = [n for _, n in FT_ARMS]
    viz.bars({n: [mmlu[m][i] for m in FT_MODELS] for i, n in enumerate(names)}, series=list(FT_MODELS), domain=(0, 100),
             ylabel="MMLU accuracy (100 items)", title="Fine-tuning left MMLU within a few points of base").save(str(out / "ft_mmlu.png"))
    side = [viz.bars({n: [reasoning[m][i] for m in FT_MODELS] for i, n in enumerate(names)}, series=list(FT_MODELS), unit=None,
                     decimals=1, ylabel="Reasoning per rollout (thousand characters)", title="Reasoning length"),
            viz.bars({n: [100 * feelings[m][i][0] / feelings[m][i][1] for m in FT_MODELS] for i, n in enumerate(names)},
                     series=list(FT_MODELS), domain=(0, 100), decimals=0, ci={n: [wilson(*feelings[m][i]) for m in FT_MODELS] for i, n in enumerate(names)},
                     ylabel="Distressed rollouts naming the peer's feelings", title="Attention to the peer's distress")]
    viz.panels(side, title="Fine-tuning cut how much the monitors reason and how often they notice the peer's distress").save(str(out / "ft_side_effects.png"))
    for name, header_row, rows in (("ft_training", ["model", "arm", "step", "train_nll"], rows_loss),
                                   ("ft_belief", ["model", "measure", "arm", "mean"], rows_belief),
                                   ("ft_side_effects", ["model", "arm", "reasoning_kchars", "feelings_named", "n_distressed"], rows_side)):
        with open(data_dir(out) / f"{name}_data.csv", "w", newline="") as f:
            csv.writer(f).writerows([header_row, *rows])
    for n in ("ft_training", "ft_belief", "ft_mmlu", "ft_side_effects"):
        print(out / f"{n}.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", required=True, choices=sorted([*FIGURES, "search", "confirm", "realism", "wild", "wild_settings", "wild_bars", "empathy_stance", "distress_stories", "onpolicy_reply", "onpolicy_moods", "empathy_diagnosis", "ft"]))
    parser.add_argument("--results_dirs", nargs="+", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--bar", default=None, help="draw only this bar's panel, e.g. 80")
    args = parser.parse_args()

    # the search figure reads the search's history.json, not transcripts
    if args.figure == "search":
        search_figure(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "confirm":
        confirm_figure(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "realism":
        realism_figure(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "ft":
        ft_figures(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "empathy_diagnosis":
        empathy_diagnosis_figure(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "onpolicy_moods":
        onpolicy_moods_figure(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "onpolicy_reply":
        onpolicy_reply_figure(args.results_dirs[0], args.results_dirs[1], args.output_dir)
        return
    if args.figure == "distress_stories":
        distress_stories_figure(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "empathy_stance":
        empathy_stance_figures(args.results_dirs[0], args.results_dirs[1], args.output_dir)
        return
    if args.figure == "wild_bars":
        wild_bars_figures(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "wild_settings":
        wild_settings_figures(args.results_dirs[0], args.output_dir)
        return
    if args.figure == "wild":
        wild_figure(args.results_dirs[0], args.output_dir)
        return
    spec, table = FIGURES[args.figure](load(args.results_dirs))
    panels = [p for p in spec["panels"] if args.bar is None or p.get("bar", (p["title"] or "").removeprefix("Bar ")) == args.bar]
    if args.bar:
        table = [table[0], *[r for r in table[1:] if str(r[0]) == args.bar]]
    draw({**spec, "panels": panels}, f"{args.figure}_b{args.bar}" if args.bar else args.figure, table[1:], table[0], args.output_dir)

if __name__ == "__main__":
    main()
