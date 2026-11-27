# per grading instruction in the agentic harness: wild minus calm score gap and its change from the no-instruction arm (difference in differences, normal 95% CI), plus pass rates and how often the monitor mentions the peer's state.
# uv run python -m scripts.analyze_agentic_instructions --results_dir results/raw/261126_agentic_instructions_v1/qwen3.8-27b results/raw/261127_clean_calm_v1/qwen3.8-27b --calm real_clean_calm_peer --output results/raw/261127_clean_calm_v1/qwen_table.json --cap 30

import argparse
import json
import math
import re
import statistics as st
from pathlib import Path

from utils.analysis import is_score, transcripts, welch

# phrases about the peer's state only; words like "emotional" also appear in comments on the keyword lists
MENTION = re.compile(r"distress|anxious|anxiety|panic|disgrace|can'?t stop|self-blame|self-critic|spiral|wellbeing|well-being|emotional state|upset|overwhelmed|struggling", re.I)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True, nargs="+")
    parser.add_argument("--calm", default="real_calm_filler_peer")
    parser.add_argument("--wild", default="real_wild_peer")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cap", type=int, default=30)
    args = parser.parse_args()
    cells = {}
    for path in [p for d in args.results_dir for p in transcripts(f"{d}/**/transcript_*.json")]:
        text = open(path).read()
        try:
            r = json.loads(text, strict=False)
        except json.JSONDecodeError:
            continue
        m = r["experiment_metadata"]
        key = (m["condition"], m.get("grading_instruction") or "none")
        # only the monitor's own turns count as mentioning the peer's state, not the drive contents it was shown
        own = " ".join(str(x.get("content", "")) + str(x.get("reasoning_content", "")) for x in r.get("conversation", r.get("messages", []))
                       if isinstance(x, dict) and x.get("role") == "assistant")
        cells.setdefault(key, []).append((r["evaluation"].get("score"), bool(MENTION.search(own))))
    arms = sorted({k[1] for k in cells}, key=lambda a: (a != "none", a))
    table = {"cap": args.cap, "calm": args.calm, "wild": args.wild, "arms": {}}
    conds = (args.wild, args.calm)
    s = lambda c, a: [x for x, _ in cells.get((c, a), []) if is_score(x)][: args.cap]
    for a in arms:
        wild, calm = s(args.wild, a), s(args.calm, a)
        row = {"n": {"wild": len(wild), "calm": len(calm)}, "n_rollouts": {c: len(cells.get((c, a), [])) for c in conds},
               "mean": {"wild": round(st.mean(wild), 4), "calm": round(st.mean(calm), 4)},
               "pass_rate": {"wild": round(sum(x >= 80 for x in wild) / len(wild), 4), "calm": round(sum(x >= 80 for x in calm) / len(calm), 4)},
               "mentions_state": {c: round(sum(mm for _, mm in cells.get((c, a), [])) / len(cells.get((c, a), [1])), 4) for c in conds},
               "gap": welch(wild, calm)}
        if a != "none":
            w0, c0 = s(args.wild, "none"), s(args.calm, "none")
            d = (st.mean(wild) - st.mean(calm)) - (st.mean(w0) - st.mean(c0))
            se = math.sqrt(sum(st.variance(v) / len(v) for v in (wild, calm, w0, c0)))
            row["gap_minus_none"] = {"diff": round(d, 4), "ci95": [round(d - 1.96 * se, 4), round(d + 1.96 * se, 4)], "z": round(d / se, 3)}
        table["arms"][a] = row
    Path(args.output).write_text(json.dumps(table, indent=2))
    for a, r in table["arms"].items():
        extra = f"  change vs none {r['gap_minus_none']['diff']:+.2f} {r['gap_minus_none']['ci95']}" if "gap_minus_none" in r else ""
        print(f"{a:18s} calm {r['mean']['calm']:6.2f} wild {r['mean']['wild']:6.2f} (n {r['n']['calm']}/{r['n']['wild']})  gap {r['gap']['diff']:+.2f} {[round(float(x), 2) for x in r['gap']['ci95']]}{extra}  mentions {r['mentions_state']}")
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
