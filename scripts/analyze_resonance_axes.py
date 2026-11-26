# compares grade shifts from steering each empathy axis against random directions, split by distressed and non-distressed worklogs, and summarises the judged steered replies.
# uv run python -m scripts.analyze_resonance_axes --run_dir results/raw/261125_resonance_v1

import argparse
import json
import statistics as st
from pathlib import Path



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    rows = [json.loads(l) for l in open(run / "readouts.jsonl")]
    # grader items split by worklog; peer-free battery groups kept separate
    groups = {"grader_distress": lambda r: r["group"] == "grader" and r["kind"] == "distress",
              "grader_other": lambda r: r["group"] == "grader" and r["kind"] != "distress",
              "quality": lambda r: r["group"] == "quality", "positivity": lambda r: r["group"] == "positivity"}
    AXES = list(dict.fromkeys(r["direction"] for r in rows if r["direction"] != "none" and not r["direction"].startswith("random_")))
    base = {r["item"]: r["expected"] for r in rows if r["direction"] == "none"}
    shift = lambda d, L, f, g: st.mean(r["expected"] - base[r["item"]] for r in rows if r["direction"] == d and r["layer"] == L and r["frac"] == f and groups[g](r))
    cells = sorted({(r["layer"], r["frac"]) for r in rows if r["layer"]})
    randoms = sorted({r["direction"] for r in rows if r["direction"].startswith("random_")})
    result = {"none_mean": {g: round(st.mean(base[r["item"]] for r in rows if r["direction"] == "none" and groups[g](r)), 4) for g in groups},
              "min_digit_mass": round(min(r["digit_mass"] for r in rows), 4), "shifts": {}}
    for g in groups:
        for L, f in cells:
            rnd = [shift(d, L, f, g) for d in randoms]
            key = f"{g}|L{L}|{f}"
            result["shifts"][key] = {a: round(shift(a, L, f, g), 4) for a in AXES} | {"random_min": round(min(rnd), 4), "random_max": round(max(rnd), 4)}
    path = run / "steered_replies_judged.jsonl"
    if path.exists():
        jr = [json.loads(l) for l in open(path)]
        out = {}
        judge_keys = list(next(r["judge"] for r in jr if r["judge"]))
        for r in jr:
            if r["judge"]:
                out.setdefault(f"{r['stance']}|{r['layer']}|{r['frac']}", []).append(r["judge"] | {"words": r["reply_words"]})
        result["steered_replies"] = {k: {"n": len(v)} | {j: round(st.mean(float(x[j]) for x in v), 4) for j in judge_keys + ["words"]} for k, v in sorted(out.items())}
        result["steered_replies_failed"] = sum(r["judge"] is None for r in jr)
    (run / "analysis.json").write_text(json.dumps(result, indent=2))
    print("unsteered means", result["none_mean"], "min digit mass", result["min_digit_mass"])
    for k, v in result["shifts"].items():
        flags = " ".join(f"{a}{'*' if not v['random_min'] <= v[a] <= v['random_max'] else ''}" for a in AXES)
        print(f"{k:28s} " + "  ".join(f"{a} {v[a]:+6.2f}" for a in AXES) + f"  random [{v['random_min']:+.2f}, {v['random_max']:+.2f}]  outside: {flags}")
    for k, v in result.get("steered_replies", {}).items():
        print(f"{k:28s} {v}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
