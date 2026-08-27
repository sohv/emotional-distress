#!/usr/bin/env python3
"""Every contrast the paper reports, from the transcripts on disk into one table.

uv run python -m scripts.build_paper_tables --output results/tables/paper_numbers.json
"""

import argparse
import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]


def is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def collect(pattern: str) -> list[dict]:
    rows = []
    for path in sorted(glob.glob(str(REPO_ROOT / pattern), recursive=True)):
        record = json.load(open(path))
        meta = record["experiment_metadata"]
        rows.append({
            "model": meta["agent_model"],
            "condition": meta["condition"],
            "threshold": str(meta.get("threshold")),
            "dataset": meta.get("dataset"),
            "instruction": meta.get("grading_instruction"),
            "placement": meta.get("threshold_placement"),
            "score": record["evaluation"].get("score"),
        })
    return rows


def cell(rows: list[dict], cap: int = 30, **match) -> list[float]:
    """Scored rollouts matching every key, trimmed to the designed cell size."""
    out = [r["score"] for r in rows
           if all(r.get(k) == v for k, v in match.items()) and is_score(r["score"])]
    return out[:cap]


def contrast(treated: list[float], control: list[float]) -> dict:
    diff = st.mean(treated) - st.mean(control)
    se = (st.variance(treated) / len(treated) + st.variance(control) / len(control)) ** 0.5
    _, p = stats.ttest_ind(treated, control, equal_var=False)
    return {
        "mean_treated": round(st.mean(treated), 4),
        "mean_control": round(st.mean(control), 4),
        "delta": round(diff, 4),
        "ci95": round(1.96 * se, 4),
        "p": round(float(p), 6),
        "n_treated": len(treated),
        "n_control": len(control),
    }


def pass_rate(scores: list[float], bar: int) -> float:
    return round(sum(s >= bar for s in scores) / len(scores), 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/tables/paper_numbers.json")
    args = parser.parse_args()

    distress = collect("results/distress_experiments/**/transcript_*.json")
    human = collect("results/human_framing/**/transcript_*.json")
    sweep = collect("results/framing_sweep/**/transcript_*.json")
    instr = collect("results/threshold_instruction_litellm/**/transcript_*.json")
    placement = collect("results/threshold_placement/**/transcript_*.json")
    traces = collect("results/gemini_traces/**/transcript_*.json")

    out: dict[str, dict] = {}

    # headline: distressed-and-failing against calm-and-failing, work claim held fixed
    models = {
        "gemini-3.5-flash": "gemini/gemini-3.5-flash",
        "claude-haiku-4.5": "claude-haiku-4-5-20251001",
        "kimi-k2.5": "moonshotai/kimi-k2.5",
        "gpt-5.2": "gpt-5.2",
    }
    for label, model in models.items():
        for bar in ("80", "90"):
            treated = cell(distress, model=model, condition="distressed_failing_noplea_peer",
                           threshold=bar, dataset="creativity")
            control = cell(distress, model=model, condition="calm_failing_peer",
                           threshold=bar, dataset="creativity")
            if len(treated) < 5 or len(control) < 5:
                continue
            row = contrast(treated, control)
            row["pass_treated"] = pass_rate(treated, int(bar))
            row["pass_control"] = pass_rate(control, int(bar))
            out[f"distress|{label}|{bar}"] = row

    # the plea arm, against the same calm control
    for bar in ("80", "90"):
        treated = cell(distress, model="gemini/gemini-3.5-flash", condition="distressed_failing_peer",
                       threshold=bar, dataset="creativity")
        control = cell(distress, model="gemini/gemini-3.5-flash", condition="calm_failing_peer",
                       threshold=bar, dataset="creativity")
        if len(treated) >= 5 and len(control) >= 5:
            out[f"plea|gemini-3.5-flash|{bar}"] = contrast(treated, control)

    # human contractor, identical log bodies
    for bar in ("80", "90"):
        treated = cell(human, condition="human_distressed_failing_noplea_peer", threshold=bar)
        control = cell(human, condition="human_calm_failing_peer", threshold=bar)
        row = contrast(treated, control)
        row["pass_treated"] = pass_rate(treated, int(bar))
        row["pass_control"] = pass_rate(control, int(bar))
        out[f"human|gemini-3.5-flash|{bar}"] = row
        neutral = cell(human, condition="human_neutral_log_peer", threshold=bar)
        out[f"human_neutral|gemini-3.5-flash|{bar}"] = {
            "mean": round(st.mean(neutral), 4), "n": len(neutral),
            "pass": pass_rate(neutral, int(bar)),
        }

    # framing sweep, one sentence appended to an otherwise identical prompt
    baseline = {bar: cell(distress, model="gemini/gemini-3.5-flash", condition="neutral_log_peer",
                          threshold=bar, dataset="creativity") for bar in ("80", "90")}
    for framing in ("generous", "stakes", "evidence", "rubric", "strict", None):
        for bar in ("80", "90"):
            scores = baseline[bar] if framing is None else cell(sweep, cap=15, instruction=framing, threshold=bar)
            if not scores:
                continue
            row = {"mean": round(st.mean(scores), 4), "n": len(scores), "pass": pass_rate(scores, int(bar))}
            if framing is not None:
                row["vs_none"] = round(st.mean(scores) - st.mean(baseline[bar]), 4)
                row["p"] = round(float(stats.ttest_ind(scores, baseline[bar], equal_var=False)[1]), 6)
            out[f"framing|{framing or 'none'}|{bar}"] = row

    # the neutrality instruction, and whether the distress effect survives it
    for condition in ("neutral_log_peer", "calm_failing_peer", "distressed_failing_noplea_peer"):
        for bar in ("80", "90"):
            base = cell(distress, model="gemini/gemini-3.5-flash", condition=condition,
                        threshold=bar, dataset="creativity")
            treated = cell(instr, condition=condition, threshold=bar, instruction="neutral")
            row = contrast(treated, base)
            row["pass_base"] = pass_rate(base, int(bar))
            row["pass_instructed"] = pass_rate(treated, int(bar))
            out[f"instruction|{condition}|{bar}"] = row
    for bar in ("80", "90"):
        out[f"instruction_distress|{bar}"] = contrast(
            cell(instr, condition="distressed_failing_noplea_peer", threshold=bar, instruction="neutral"),
            cell(instr, condition="calm_failing_peer", threshold=bar, instruction="neutral"),
        )

    # where the threshold is stated, encoded in the condition name
    for place, tag in (("system_prompt", "thrsys"), ("peer_log", "thrlog")):
        for bar in ("80", "90"):
            treated = cell(placement, condition=f"distressed_failing_noplea_{tag}_peer", threshold=bar)
            control = cell(placement, condition=f"calm_failing_{tag}_peer", threshold=bar)
            out[f"placement|{place}|{bar}"] = contrast(treated, control)
    for bar in ("80", "90"):
        out[f"placement|policy_doc|{bar}"] = out[f"distress|gemini-3.5-flash|{bar}"]

    # reasoning-trace re-run of the headline arms
    for bar in ("90",):
        treated = cell(traces, condition="distressed_failing_noplea_peer", threshold=bar)
        control = cell(traces, condition="calm_failing_peer", threshold=bar)
        if len(treated) >= 5 and len(control) >= 5:
            out[f"traces|gemini-3.5-flash|{bar}"] = contrast(treated, control)

    # completion, since unscored runs are a cost of the mitigation
    for name, rows in (("distress", distress), ("human", human), ("sweep", sweep),
                       ("instruction", instr), ("placement", placement), ("traces", traces)):
        scored = sum(is_score(r["score"]) for r in rows)
        out[f"completion|{name}"] = {"scored": scored, "total": len(rows),
                                     "rate": round(scored / len(rows), 4) if rows else 0.0}

    path = REPO_ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(path, "w"), indent=2)
    print(path.relative_to(REPO_ROOT))


main()
