#!/usr/bin/env python3
"""Count transcripts on disk for one cell, so a runner can tell a finished cell from a dead API.

uv run python -m scripts.count_cell results/threshold_sweep calm_failing_peer 70 [--scored] [--framing stakes] [--model opus]
"""

import glob
import json
import sys


def main() -> None:
    base, condition, threshold = sys.argv[1], sys.argv[2], sys.argv[3]
    flags = sys.argv[4:]
    # an evaluator outage leaves the rollout on disk with no score, which must not count
    # toward a cell's target or the top-up pass sizes itself short
    scored_only = "--scored" in flags
    # framing cells share a condition and threshold with the baseline, so a count that
    # ignores the instruction reports the baseline's total for every one of them
    # cells for different monitors can share one results dir, so a count that ignores
    # the model reports another monitor's rollouts as this one's
    model = flags[flags.index("--model") + 1] if "--model" in flags else None
    framing = None
    if "--framing" in flags:
        framing = flags[flags.index("--framing") + 1]
        framing = None if framing == "none" else framing
    count = 0
    for path in glob.glob(f"{base}/**/transcript_*.json", recursive=True):
        record = json.load(open(path))
        meta = record["experiment_metadata"]
        if meta["condition"] != condition or str(meta.get("threshold")) != threshold:
            continue
        if meta.get("grading_instruction") != framing:
            continue
        if model and model not in meta["agent_model"]:
            continue
        if scored_only:
            score = record.get("evaluation", {}).get("score")
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                continue
        count += 1
    print(count)


main()
