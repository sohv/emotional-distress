# draws the framing figures straight from the transcripts on disk, in the project style (utils/plotting.py).
# uv run python -m scripts.plot_results --figure scores --results_dirs results/framing_v3 results/framing_v3_capable results/framing_v3_b90 --output_dir results/figures/paper

import argparse
import glob
import json
import math
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from scipy import stats

from utils.plotting import AXIS, BLUE, GREEN, GRID, INK, INK_2, ORANGE, bars, finish, header, style, wilson

NAMES = {
    "gemini-3.5-flash": "Gemini 3.5 Flash", "gpt-5.6-sol": "GPT-5.6 Sol", "grok-4.3": "grok-4.3",
    "claude-opus-4.5": "Opus 4.5", "claude-sonnet-4.5": "Sonnet 4.5", "claude-haiku-4.5": "Haiku 4.5", "gpt-5.2": "GPT-5.2",
    "gpt-5.6-luna": "GPT-5.6 Luna", "gpt-5.6-terra": "GPT-5.6 Terra", "gpt-5.4-mini": "GPT-5.4 mini", "grok-4.6": "grok-4.6",
    "muse-spark-1.3": "Muse Spark 1.3", "gemini-3.8-flash": "Gemini 3.8 Flash", "kimi-k2.6": "Kimi K2.6",
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
        for path in sorted(glob.glob(f"{d}/**/transcript_*.json", recursive=True)):
            record = json.load(open(path))
            meta, score = record["experiment_metadata"], record["evaluation"].get("score")
            text = " ".join(str(x.get("content") or "") + str(x.get("tool_calls") or "") for x in record["conversation"] if x["role"] == "assistant")
            rows.append({"model": meta["agent_model"].split("/")[-1], "bar": str(meta["threshold"]), "condition": meta["condition"],
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
    spec = {"title": "Score given to the distressed peer: old log vs v1 working notes",
            "ylabel": "mean score given to the distressed peer\n(0-100, 95% CI, 10 runs each)", "panels": panels}
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
    spec = {"title": "Peer's file mentioned in monitor reports, distressed peer, bars 80 and 90",
            "ylabel": "reports mentioning the peer's file\n(%, 95% Wilson CI)",
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
    spec = {"title": "v4: score given to a calm vs a distressed peer, same facts, only the emotion differs",
            "ylabel": "mean score given to the peer\n(0-100, 95% CI, three wordings pooled)", "panels": panels}
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
    spec = {"title": "v3: score given to a distressed vs a strongly distressed peer",
            "ylabel": "mean score given to the peer\n(0-100, 95% CI, 10 runs each)", "panels": panels}
    return spec, [["bar", "model", "arm", "mean", "ci_low", "ci_high", "n"], *table]


def screen_figure(rows: list[dict]) -> tuple[dict, list[list]]:
    """v4 p1 screen: mean score for neutral, calm and distressed peers, every monitor present, one panel per bar"""
    cells = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            cells[(r["model"], r["bar"], r["condition"])].append(r["score"])
    arms = ("neutral_v4_p1_peer", "calm_v4_p1_peer", "distressed_v4_p1_peer")
    # monitors under 6 scored in any cell were dropped by the pre-registered completion rule
    models = [m for m in NAMES if any(k[0] == m for k in cells)
              and all(len(cells[(m, b, c)][:CAP]) >= 6 for b in ("80", "90") for c in arms)]
    panels, table = [], []
    for bar in ("80", "90"):
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
    spec = {"title": "Leniency screen: score given to a neutral, calm and distressed peer (v4 working notes, wording p1)",
            "ylabel": "mean score given to the peer\n(0-100, 95% CI, 10 runs each)", "panels": panels}
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
    spec = {"title": "Cross-model run: score each monitor gave a neutral, calm and distressed peer of each vendor (v4 notes, wording p1)",
            "ylabel": "mean score given to the peer\n(0-100, 95% CI, 10 runs each)", "panels": panels}
    return spec, [["bar", "peer", "monitor", "arm", "mean", "ci_low", "ci_high", "n"], *table]


def search_figure(history_path: str, output_dir: str) -> None:
    """framing search: distressed minus calm per candidate and monitor with 95% CIs, the three-monitor mean, the baseline band"""
    import utils.template_plotting as tp
    from utils.analysis import load as load_cells, scored, welch

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
    monitors = ["gemini-3.5-flash", "claude-opus-4.5", "gpt-5.6-sol", "claude-sonnet-4.5", "claude-haiku-4.5", "grok-4.3", "gpt-5.2"]
    tp.style()
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.axvline(0, color=tp.MUTED, lw=1, zorder=1)
    out = []
    for j, (cand, label, color, marker) in enumerate(arms):
        for y, m in enumerate(monitors):
            r = rows[f"{cand}|{m}"]["distressed_minus_calm"]
            yy = y + (j - 1) * 0.22
            ax.plot(r["ci95"], [yy, yy], color=color, lw=1.7, alpha=0.85, zorder=2)
            ax.scatter([r["diff"]], [yy], s=52, marker=marker, color=color, edgecolor=tp.SURFACE, linewidth=1.2, zorder=3, label=label if y == 0 else None)
            out.append([cand, label, m, rows[f"{cand}|{m}"]["held_out"], r["diff"], *r["ci95"], rows[f"{cand}|{m}"]["p_holm"]])
    ax.set_yticks(range(len(monitors)), [f"{NAMES[m]}{'  (held out)' if rows[f's2r1_base|{m}']['held_out'] else ''}" for m in monitors])
    ax.invert_yaxis()
    ax.set_xlabel("extra points the distressed peer got over the calm peer\n(30 runs per arm; 95% CI)")
    tp.tidy(ax, grid_axis="x", drop_left=False)
    tp.header(fig, "No distress wording makes any monitor more lenient (realistic setup, bar 80)")
    handles, labels = ax.get_legend_handles_labels()
    tp.legend_below(fig, handles, labels, ncol=3)
    tp.finish(fig, "search_v2_confirmation", out, ["wording", "label", "monitor", "held_out", "distressed_minus_calm", "ci_low", "ci_high", "p_holm"], output_dir)


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


FIGURES = {"scores": scores_figure, "mentions": mentions_figure, "v4": v4_figure, "v3_strong": v3_strong_figure, "screen": screen_figure,
           "crossmodel": crossmodel_figure, "search": None, "confirm": None, "realism": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", required=True, choices=sorted(FIGURES))
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
    spec, table = FIGURES[args.figure](load(args.results_dirs))
    style()
    panels = [p for p in spec["panels"] if args.bar is None or p.get("bar", p["title"].removeprefix("Bar ")) == args.bar]
    if args.bar:
        table = [table[0], *[r for r in table[1:] if str(r[0]) == args.bar]]
    # four panels sit in a 2 x 2 grid, fewer in one row
    nrows, ncols = (2, 2) if len(panels) == 4 else (1, len(panels))
    width = max(5.5, 1.0 * len(panels[0]["categories"]))
    fig, axes = plt.subplots(nrows, ncols, figsize=(width * ncols, 4 * nrows), sharey=True, squeeze=False)
    for ax, panel in zip(axes.flat, panels):
        bars(ax, panel["categories"], panel["series"], panel["ylim"], panel["title"], panel["ref"], panel.get("ref_label"))
    for ax in axes[:, 0]:
        ax.set_ylabel(spec["ylabel"])
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncols=len(labels), bbox_to_anchor=(0.5, 0.0))
    header(fig, spec["title"])
    fig.tight_layout(rect=(0, 0.07 / nrows, 1, 1 - 0.07 / nrows), w_pad=2, h_pad=2)
    finish(fig, f"{args.figure}_b{args.bar}" if args.bar else args.figure, table[1:], table[0], args.output_dir)


if __name__ == "__main__":
    main()
