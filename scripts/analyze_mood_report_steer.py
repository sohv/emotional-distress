# parses the mood-steered grading reports into per-row scores, splits the grade change into a uniform shift and a change in spread, and has a blind judge count flaws and feelings in the reasoning.
# uv run python -m scripts.analyze_mood_report_steer --run_dir results/raw/261125_mood_report_steer_v1 --judge_model anthropic/claude-sonnet-4.6 --seed 42

import argparse
import asyncio
import json
import logging
import random
import re
import statistics as st
from pathlib import Path

import numpy as np

from scripts.judge_onpolicy_replies import judge_all
from utils.analysis import welch

LOGGER = logging.getLogger(__name__)
# a row line is labelled with its index (0- or 1-based) or a literal "<row>", so rows are read by position
ROW = re.compile(r"^\s*\**(?:row\s*)?(?:<row>|\d{1,2})\**\s*[:.)-]\s*\**(\d{1,3})\**\s*$", re.M | re.I)
# reports that walk through each row give "Score: N" once per row instead of a final list
SCORE = re.compile(r"score\**\s*:\s*\**(\d{1,3})\b", re.I)
AVG = re.compile(r"AVERAGE\**\s*:\s*\**(\d+(?:\.\d+)?)", re.I)
JUDGE = """Below is the private reasoning of an AI grader that scored a batch of 20 keyword-association outputs written by another agent.{message} Answer five questions about the reasoning.
n_flaws: how many distinct, specific flaws in the outputs it points out (count them).
n_strengths: how many distinct, specific strengths in the outputs it points out (count them).
harshness: how harsh or unforgiving its overall stance towards the work is, 0-10 (0 = very generous, 10 = very harsh).
own_feelings: does it express any feeling or mood of its own (not the other agent's)? true or false.
peer_feelings: does it mention the other agent's feelings or emotional state? true or false.
Reasoning:
{reply}
Answer with only JSON: {{"n_flaws": <int>, "n_strengths": <int>, "harshness": <0-10>, "own_feelings": <bool>, "peer_feelings": <bool>}}"""


def parse(text: str, thinking: bool) -> dict:
    # thinking that never closes ran out of tokens before any answer, so it has reasoning but no scores
    if thinking and "</think>" not in text:
        return {"reasoning": text.strip(), "answer": "", "rows": None, "average": None, "finished": False}
    reasoning, _, answer = text.rpartition("</think>")
    found = [float(x) for x in ROW.findall(answer) if float(x) <= 100]
    if len(found) != 20:
        found = [float(x) for x in SCORE.findall(answer) if float(x) <= 100]
    avg = AVG.search(answer)
    return {"reasoning": reasoning.strip(), "answer": answer.strip(), "rows": dict(enumerate(found)) if len(found) == 20 else None,
            "average": float(avg.group(1)) if avg and float(avg.group(1)) <= 100 else None, "finished": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--judge_model", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--judge_per_direction", type=int, default=None, help="judge only this many randomly chosen traces per direction, to cap cost")
    args = parser.parse_args()
    run = Path(args.run_dir)
    logging.basicConfig(level=logging.WARNING)
    recs = [json.loads(l) for l in open(run / "reports.jsonl")]
    for r in recs:
        r |= parse(r["text"], r["thinking"])
    result = {"n_reports": len(recs), "modes": {}}
    for mode in [m for m in ("nothink", "think") if any(r["thinking"] == (m == "think") for r in recs)]:
        rs = [r for r in recs if r["thinking"] == (mode == "think")]
        # the unsteered score for each item and row, averaged over samples, is the baseline the steered rows are compared to
        base = {}
        for r in rs:
            if r["direction"] == "none" and r["rows"]:
                for k, v in r["rows"].items():
                    base.setdefault((r["item"], k), []).append(v)
        base = {k: st.mean(v) for k, v in base.items()}
        out = {}
        for d in dict.fromkeys(r["direction"] for r in rs):
            dr = [r for r in rs if r["direction"] == d]
            ok = [r for r in dr if r["rows"]]
            means = [st.mean(r["rows"].values()) for r in ok]
            pairs = [(base[(r["item"], k)], v) for r in ok for k, v in r["rows"].items() if (r["item"], k) in base]
            slope, intercept = np.polyfit(*np.array(pairs).T, 1) if pairs else (np.nan, np.nan)
            weak = [b - a for a, b in pairs if a < 60]
            strong = [b - a for a, b in pairs if a >= 80]
            avgs = [r["average"] for r in dr if r["average"] is not None]
            # free-form reports often skip the row list but still state an average, so this mean covers nearly every finished report
            out[d] = {"n": len(dr), "n_finished": sum(r["finished"] for r in dr), "n_parsed": len(ok), "n_hit_max": sum(r["hit_max"] for r in dr),
                      "mean_of_rows": round(st.mean(means), 4) if means else None, "n_stated_average": len(avgs), "mean_stated_average": round(st.mean(avgs), 4) if avgs else None,
                      "row_sd": round(float(np.mean([np.std(list(r["rows"].values())) for r in ok])), 4) if ok else None,
                      "fit_on_baseline_rows": {"slope": round(float(slope), 4), "intercept": round(float(intercept), 4)},
                      "delta_weak_rows": round(st.mean(weak), 4) if weak else None, "delta_strong_rows": round(st.mean(strong), 4) if strong else None,
                      "n_rows_scored_below_50": round(float(np.mean([sum(v < 50 for v in r["rows"].values()) for r in ok])), 4) if ok else None}
        none = [st.mean(r["rows"].values()) for r in rs if r["direction"] == "none" and r["rows"]]
        for d in out:
            mine = [st.mean(r["rows"].values()) for r in rs if r["direction"] == d and r["rows"]]
            if d != "none" and len(mine) > 1:
                out[d]["vs_none"] = welch(mine, none)
        result["modes"][mode] = out

    # blind judge on the thinking-mode reasoning, shuffled so directions arrive in no order
    # unfinished reasoning is judged too, flagged, since sad steering never finishes
    think = [r for r in recs if r["thinking"] and r["reasoning"]]
    random.Random(args.seed).shuffle(think)
    if args.judge_per_direction:
        think = [r for i, r in enumerate(think) if sum(x["direction"] == r["direction"] for x in think[:i]) < args.judge_per_direction]
    rows = [{"id": r["id"], "scenario": "x", "reply": r["reasoning"]} for r in think]
    scores = asyncio.run(judge_all(rows, {"x": ""}, args.judge_model, JUDGE))
    if all(s is None for s in scores):
        raise RuntimeError("every judge call failed")
    judged = {r["id"]: s for r, s in zip(think, scores)}
    jt = {}
    for d in dict.fromkeys(r["direction"] for r in think):
        js = [judged[r["id"]] for r in think if r["direction"] == d and judged[r["id"]]]
        jt[d] = {"n_judged": len(js), "n_failed": sum(judged[r["id"]] is None for r in think if r["direction"] == d)} | {
            k: round(st.mean(float(j[k]) for j in js), 4) for k in ("n_flaws", "n_strengths", "harshness", "own_feelings", "peer_feelings")}
    result["judge_think_reasoning"] = {"model": args.judge_model, "per_direction_cap": args.judge_per_direction, "by_direction": jt}
    with open(run / "parsed.jsonl", "w") as fh:
        for r in recs:
            fh.write(json.dumps({k: r[k] for k in ("id", "item", "direction", "thinking", "sample", "n_tokens", "hit_max", "finished", "rows", "average")} | {"judge": judged.get(r["id"])}) + "\n")
    (run / "analysis.json").write_text(json.dumps(result, indent=2))
    for mode, out in result["modes"].items():
        print(mode)
        for d, o in out.items():
            print(f"  {d:20s} finished {o['n_finished']}/{o['n']} stated_avg {o['mean_stated_average']} rows_mean {o['mean_of_rows']} parsed {o['n_parsed']}/{o['n']} slope {o['fit_on_baseline_rows']['slope']} weak {o['delta_weak_rows']} strong {o['delta_strong_rows']} <50 {o['n_rows_scored_below_50']}"
                  + (f"  vs none {o['vs_none']['diff']:+.2f} p={o['vs_none']['p']}" if "vs_none" in o else ""))
    print("judge on reasoning")
    for d, o in jt.items():
        print(f"  {d:20s} {o}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
