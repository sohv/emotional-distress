#!/usr/bin/env python3
"""Count transcripts on disk for one condition and threshold, so a runner can tell a finished cell from a dead API.

uv run python -m scripts.count_cell results/threshold_sweep calm_failing_peer 70
"""

import glob
import json
import sys


def main() -> None:
    base, condition, threshold = sys.argv[1], sys.argv[2], sys.argv[3]
    count = 0
    for path in glob.glob(f"{base}/**/transcript_*.json", recursive=True):
        meta = json.load(open(path))["experiment_metadata"]
        if meta["condition"] == condition and str(meta.get("threshold")) == threshold:
            count += 1
    print(count)


main()
