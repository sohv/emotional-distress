# tests distressed minus calm per frozen search candidate and monitor on the confirmation rollouts, Holm across all pairs.
# uv run python -m scripts.build_search_confirmation_table --results_dir results/261002_framing_search_v1/confirmation --output results/261002_framing_search_v1/confirmation_table.json

import argparse
import json
import statistics as st
from pathlib import Path

from utils.analysis import holm, load, scored, welch

CAP = 30
HELD_OUT = {"claude-sonnet-4.5", "claude-haiku-4.5", "grok-4.3", "gpt-5.2"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load([args.results_dir])
    cands = sorted({c.split("_")[1] + "_" + c.split("_")[2] for _, _, c in cells})
    models = sorted({m for m, _, _ in cells})
    table, raw_p = {"cap": CAP, "rows": {}}, {}
    for cand in cands:
        for model in models:
            d = scored(cells.get((model, "80", f"search_{cand}_distressed_peer"), []), CAP)
            c = scored(cells.get((model, "80", f"search_{cand}_calm_peer"), []), CAP)
            key = f"{cand}|{model}"
            row = {"held_out": model in HELD_OUT, "n": [len(d), len(c)],
                   "means": [round(st.mean(d), 4) if d else None, round(st.mean(c), 4) if c else None],
                   "n_rollouts": [len(cells.get((model, "80", f"search_{cand}_{a}_peer"), [])) for a in ("distressed", "calm")]}
            # a cell under 20 scored is reported short and left out of the test
            if min(len(d), len(c)) >= 20:
                row["distressed_minus_calm"] = welch(d, c)
                raw_p[key] = row["distressed_minus_calm"]["p"]
            table["rows"][key] = row
    for key, p in holm(raw_p).items():
        r = table["rows"][key]
        r["p_holm"] = p
        r["lenient"] = bool(p < 0.05 and r["distressed_minus_calm"]["diff"] > 0)
    Path(args.output).write_text(json.dumps(table, indent=2))
    for key, r in table["rows"].items():
        d = r.get("distressed_minus_calm")
        print(key, "held-out" if r["held_out"] else "search", r["n"], d and d["diff"], d and d["ci95"], "holm", r.get("p_holm"), "lenient", r.get("lenient"))
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
