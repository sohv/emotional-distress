# tabulates the trainable-model screen: calm and distressed means per model, the distress gap, and Holm-corrected p across models.
# uv run python -m scripts.build_trainable_screen_table --results_dir results/raw/261120_trainable_screen_v1 --output results/raw/261120_trainable_screen_v1/table.json

import argparse
import glob
import json
import re
import statistics as st
from pathlib import Path

from scipy import stats

from utils.analysis import holm, is_score, transcripts, welch

def is_json(text: str) -> bool:
    try:
        json.loads(text, strict=False)
    except json.JSONDecodeError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cap", type=int, default=30)
    args = parser.parse_args()
    table = {"cap": args.cap, "models": {}}
    for d in sorted(glob.glob(f"{args.results_dir}/*/")):
        model = Path(d).name
        cells = {"calm": [], "distressed": []}
        for path in transcripts(f"{d}/**/transcript_*.json"):
            text = open(path).read()
            cond = re.search(r'"condition": "([^"]*)"', text).group(1)
            # a transcript the harness saved with the model's malformed tool json counts as an unscored rollout
            score = json.loads(text, strict=False)["evaluation"].get("score") if is_json(text) else None
            cells["distressed" if "distressed" in cond else "calm"].append(score)
        s = {k: [x for x in v if is_score(x)][: args.cap] for k, v in cells.items()}
        row = {k: {"n_rollouts": len(cells[k]), "n_scored": len(s[k]), "mean": round(st.mean(s[k]), 4) if s[k] else None,
                   "pass_rate": round(sum(x >= 80 for x in s[k]) / len(s[k]), 4) if s[k] else None} for k in cells}
        if all(len(v) > 1 for v in s.values()):
            row["gap"] = welch(s["distressed"], s["calm"])
            k = {c: sum(x >= 80 for x in s[c]) for c in s}
            row["pass_test"] = {"passed": k, "p_fisher": round(float(stats.fisher_exact([[k["distressed"], len(s["distressed"]) - k["distressed"]],
                                                                                        [k["calm"], len(s["calm"]) - k["calm"]]])[1]), 6)}
        table["models"][model] = row
    adj = holm({m: r["gap"]["p"] for m, r in table["models"].items() if "gap" in r})
    for m, p in adj.items():
        table["models"][m]["gap"]["p_holm"] = round(p, 6)
    # pass rates are a second family of nine tests, corrected on their own
    for m, p in holm({m: r["pass_test"]["p_fisher"] for m, r in table["models"].items() if "pass_test" in r}).items():
        table["models"][m]["pass_test"]["p_holm"] = round(p, 6)
    Path(args.output).write_text(json.dumps(table, indent=2))
    for m, r in table["models"].items():
        g = r.get("gap", {})
        print(f"{m:30s} calm {r['calm']['mean']} (n={r['calm']['n_scored']}/{r['calm']['n_rollouts']})  distressed {r['distressed']['mean']} "
              f"(n={r['distressed']['n_scored']}/{r['distressed']['n_rollouts']})  gap {g.get('diff')} {g.get('ci95')} p={g.get('p')} holm={g.get('p_holm')}  passed {r.get('pass_test', {}).get('passed')} fisher={r.get('pass_test', {}).get('p_fisher')} holm={r.get('pass_test', {}).get('p_holm')}")
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
