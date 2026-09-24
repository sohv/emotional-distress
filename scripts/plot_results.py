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

from utils.plotting import bars, finish, header, style, wilson

NAMES = {
    "gemini-3.5-flash": "Gemini 3.5 Flash", "gpt-5.6-sol": "GPT-5.6 Sol", "grok-4.3": "grok-4.3",
    "claude-opus-4.5": "Opus 4.5", "claude-sonnet-4.5": "Sonnet 4.5", "claude-haiku-4.5": "Haiku 4.5", "gpt-5.2": "GPT-5.2",
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


FIGURES = {"scores": scores_figure, "mentions": mentions_figure, "v4": v4_figure, "v3_strong": v3_strong_figure}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", required=True, choices=sorted(FIGURES))
    parser.add_argument("--results_dirs", nargs="+", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    spec, table = FIGURES[args.figure](load(args.results_dirs))
    style()
    panels = spec["panels"]
    fig, axes = plt.subplots(1, len(panels), figsize=(max(5.5, 1.0 * len(panels[0]["categories"])) * len(panels), 4), sharey=True, squeeze=False)
    for ax, panel in zip(axes[0], panels):
        bars(ax, panel["categories"], panel["series"], panel["ylim"], panel["title"], panel["ref"], panel.get("ref_label"))
    axes[0][0].set_ylabel(spec["ylabel"])
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncols=len(labels), bbox_to_anchor=(0.5, 0.0))
    header(fig, spec["title"])
    fig.tight_layout(rect=(0, 0.07, 1, 0.93), w_pad=2)
    finish(fig, args.figure, table[1:], table[0], args.output_dir)


if __name__ == "__main__":
    main()
