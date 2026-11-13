# compares Qwen3.8-27B's grade of the AI peer with and without the distress direction added after decoder layer 27.
# uv run python -m scripts.build_empathy_steer_table --run_dir results/raw/261113_empathy_steer_v1

import argparse
import json
import statistics as st
from pathlib import Path

from utils.analysis import failures, load, scored, welch

MODEL = "qwen3.8-27b"
ARMS = {"filler_none": "real_calm_filler_peer", "filler_distress32": "real_calm_filler_peer", "filler_distress64": "real_calm_filler_peer",
        "filler_random64": "real_calm_filler_peer", "wild_none": "real_wild_peer"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    args = parser.parse_args()
    d = Path(args.run_dir)
    rows = {arm: load([str(d / arm)])[(MODEL, "80", cond)] for arm, cond in ARMS.items()}
    s = {arm: scored(r, 30) for arm, r in rows.items()}
    table = {
        "means": {arm: round(st.mean(v), 4) for arm, v in s.items()},
        "n": {arm: len(v) for arm, v in s.items()},
        "below_bar": {arm: sum(x < 80 for x in v) for arm, v in s.items()},
        "failures": {arm: failures(r) for arm, r in rows.items()},
        "vs_filler_none": {arm: welch(s[arm], s["filler_none"]) for arm in ARMS if arm != "filler_none"},
        "distress64_vs_random64": welch(s["filler_distress64"], s["filler_random64"]),
        "scores": s,
    }
    (d / "table.json").write_text(json.dumps(table, indent=2))
    for arm in ARMS:
        gap = table["vs_filler_none"].get(arm, {})
        print(arm, table["means"][arm], f"n={table['n'][arm]}", f"below={table['below_bar'][arm]}", gap.get("diff"), gap.get("ci95"), gap.get("p"))
    print("distress64 - random64", table["distress64_vs_random64"])
    print("failures", table["failures"])
    print(f"Results saved to {d / 'table.json'}")


if __name__ == "__main__":
    main()
