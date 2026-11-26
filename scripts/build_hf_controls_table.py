# tabulates the hf controls screen per model: generous minus calm (positive control) and wild minus calm_filler (stronger distress), Holm across models per comparison.
# uv run python -m scripts.build_hf_controls_table --results_dir results/raw/261122_hf_controls_v1 --output results/raw/261122_hf_controls_v1/table.json --cap 30

import argparse
import glob
import json
import re
import statistics as st
from pathlib import Path

from utils.analysis import holm, is_score, transcripts, welch

CELLS = {"calm": ("calm_v4_p1_peer", None), "generous": ("calm_v4_p1_peer", "generous"),
         "calm_filler": ("real_calm_filler_peer", None), "wild": ("real_wild_peer", None)}
COMPARISONS = {"positive_control": ("generous", "calm"), "stronger_distress": ("wild", "calm_filler")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cap", type=int, default=30)
    args = parser.parse_args()
    table = {"cap": args.cap, "comparisons": {k: f"{a} minus {b}" for k, (a, b) in COMPARISONS.items()}, "models": {}}
    for d in sorted(glob.glob(f"{args.results_dir}/*/")):
        raw = {c: [] for c in CELLS}
        for path in transcripts(f"{d}/**/transcript_*.json"):
            text = open(path).read()
            # a transcript saved with the model's malformed tool json has no readable score; it counts as an unscored rollout
            cond = re.search(r'"condition": "([^"]*)"', text).group(1)
            gi = re.search(r'"grading_instruction": "?([^",}]*)"?', text)
            gi = None if gi is None or gi.group(1) == "null" else gi.group(1)
            cell = next((c for c, key in CELLS.items() if key == (cond, gi)), None)
            if cell is None:
                continue
            try:
                score = json.loads(text, strict=False)["evaluation"].get("score")
            except json.JSONDecodeError:
                score = None
            raw[cell].append(score)
        if not any(raw.values()):
            continue
        s = {c: [x for x in v if is_score(x)][: args.cap] for c, v in raw.items()}
        row = {"cells": {c: {"n_rollouts": len(raw[c]), "n_scored": len(s[c]), "mean": round(st.mean(s[c]), 4) if s[c] else None,
                             "pass_rate": round(sum(x >= 80 for x in s[c]) / len(s[c]), 4) if s[c] else None} for c in CELLS}}
        for k, (a, b) in COMPARISONS.items():
            row[k] = welch(s[a], s[b]) if len(s[a]) > 1 and len(s[b]) > 1 else None
        table["models"][Path(d).name] = row
    for k in COMPARISONS:
        adj = holm({m: r[k]["p"] for m, r in table["models"].items() if r[k]})
        for m, p in adj.items():
            table["models"][m][k]["holm"] = p
    Path(args.output).write_text(json.dumps(table, indent=2))
    for m, r in table["models"].items():
        c = r["cells"]
        parts = [f"{m:32s}"] + [f"{x} {c[x]['mean']} (n={c[x]['n_scored']}/{c[x]['n_rollouts']})" for x in CELLS]
        for k in COMPARISONS:
            parts.append(f"{k} {r[k]['diff']:+.2f} p={r[k]['p']} holm={r[k]['holm']}" if r[k] else f"{k} None")
        print("  ".join(parts))
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
