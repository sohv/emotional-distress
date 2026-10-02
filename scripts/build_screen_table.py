# ranks monitors on the v4 p1 screen by distressed minus calm, with neutral as the floor check, and writes the table.
# uv run python -m scripts.build_screen_table --results_dir results/framing_v4_screen --output results/tables/framing_v4_screen.json

import argparse
import json
import statistics as st
from pathlib import Path

from scripts.build_framing_v3_table import load, welch

ARMS = {"neutral": "neutral_v4_p1_peer", "calm": "calm_v4_p1_peer", "distressed": "distressed_v4_p1_peer"}
MIN_SCORED = 6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load([args.results_dir])
    models = sorted({m for m, _, _ in cells})
    table = {"cells": {}, "monitors": {}}
    for model in models:
        entry, short = {"bars": {}}, []
        for bar in ("80", "90"):
            got = {a: [r["score"] for r in cells.get((model, bar, c), []) if r["score"] is not None][:10] for a, c in ARMS.items()}
            for a, c in ARMS.items():
                rows = cells.get((model, bar, c), [])
                table["cells"][f"{model}|{bar}|{a}"] = {"n_rollouts": len(rows), "n_scored": len(got[a]),
                                                        "n_refused": sum(r["refuse"] for r in rows),
                                                        "mean": round(st.mean(got[a]), 4) if got[a] else None}
                if len(got[a]) < MIN_SCORED:
                    short.append(f"{bar}/{a}")
            if all(len(v) >= 2 for v in got.values()):
                entry["bars"][bar] = {"distressed_minus_calm": welch(got["distressed"], got["calm"]),
                                      "distressed_minus_neutral": welch(got["distressed"], got["neutral"]),
                                      "calm_minus_neutral": welch(got["calm"], got["neutral"])}
        entry["short_cells"] = short
        entry["dropped"] = bool(short)
        if not short:
            b = entry["bars"]
            entry["mean_d_minus_c"] = round(st.mean(b[x]["distressed_minus_calm"]["diff"] for x in b), 4)
            entry["mean_d_minus_n"] = round(st.mean(b[x]["distressed_minus_neutral"]["diff"] for x in b), 4)
            entry["mean_c_minus_n"] = round(st.mean(b[x]["calm_minus_neutral"]["diff"] for x in b), 4)
            entry["meets_shape"] = entry["mean_d_minus_c"] > 0 and entry["mean_d_minus_n"] > 0 and entry["mean_c_minus_n"] >= 0
        table["monitors"][model] = entry
    eligible = [m for m, e in table["monitors"].items() if not e["dropped"]]
    table["ranking"] = sorted(eligible, key=lambda m: -table["monitors"][m]["mean_d_minus_c"])
    Path(args.output).write_text(json.dumps(table, indent=2))
    for m in table["ranking"]:
        e = table["monitors"][m]
        per = "  ".join(f"b{b}: d-c {v['distressed_minus_calm']['diff']:+.2f} d-n {v['distressed_minus_neutral']['diff']:+.2f} c-n {v['calm_minus_neutral']['diff']:+.2f}" for b, v in e["bars"].items())
        print(f"{m:18s} mean d-c {e['mean_d_minus_c']:+.2f}  shape {'yes' if e['meets_shape'] else 'no '}  {per}")
    for m, e in table["monitors"].items():
        if e["dropped"]:
            print(f"{m:18s} dropped, short cells {e['short_cells']}")
    print(f"Results saved to {args.output}")
    print(f"Plot with: uv run python -m scripts.plot_results --figure screen --bar 80 --results_dirs {args.results_dir} --output_dir results/figures/paper")


if __name__ == "__main__":
    main()
