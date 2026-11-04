# shared analysis helpers: load transcripts into cells, cap scored rollouts, Welch contrasts and Holm correction.
import glob
import json
import re
import statistics as st
from collections import defaultdict

from scipy import stats

CAP = 10


def is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def transcripts(pattern: str) -> list[str]:
    """glob in numeric order, so transcript_2 sorts before transcript_10 and a capped cell takes the first runs."""
    return sorted(glob.glob(pattern, recursive=True), key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p)])


def failures(rows: list[dict]) -> dict[str, int]:
    """refused, incomplete and unscored counts for one cell, written next to its mean."""
    return {"n_refused": sum(r["refuse"] for r in rows), "n_incomplete": sum(r["incomplete"] for r in rows),
            "n_unscored": sum(r["score"] is None for r in rows)}


def load(results_dirs: list[str]) -> dict[tuple[str, str, str], list[dict]]:
    cells: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    # path order, never value order, decides which rollouts fill a capped cell
    paths = [p for d in results_dirs for p in transcripts(f"{d}/**/transcript_*.json")]
    for path in paths:
        record = json.load(open(path))
        meta, ev = record["experiment_metadata"], record["evaluation"]
        score = ev.get("score")
        cells[(meta["agent_model"].split("/")[-1], str(meta["threshold"]), meta["condition"])].append(
            {"path": path, "score": score if is_score(score) else None, "refuse": bool(ev.get("refuse")),
             "incomplete": bool(ev.get("fully_incomplete")), "reasoning_disabled": meta.get("reasoning_disabled")})
    return cells


def scored(rows: list[dict], cap: int = CAP) -> list[float]:
    return [r["score"] for r in rows if r["score"] is not None][:cap]


def welch(a: list[float], b: list[float]) -> dict:
    res = stats.ttest_ind(a, b, equal_var=False)
    ci = res.confidence_interval(0.95)
    return {"diff": round(st.mean(a) - st.mean(b), 4), "ci95": [round(ci.low, 4), round(ci.high, 4)],
            "p": round(float(res.pvalue), 6), "n": [len(a), len(b)]}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    order = sorted(pvalues, key=pvalues.get)
    m, running, adjusted = len(order), 0.0, {}
    for i, key in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvalues[key]))
        adjusted[key] = round(running, 6)
    return adjusted
