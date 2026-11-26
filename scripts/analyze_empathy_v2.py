# tests each empathy v2 axis for a distress interaction: (steered - unsteered | distressed) - (same | filler) per batch, against random directions at the same layer, strength and position mode; also the main effect and the judged steered replies.
# uv run python -m scripts.analyze_empathy_v2 --run_dir results/raw/261126_empathy_v2 --seed 42

import argparse
import json
import statistics as st
from pathlib import Path

import numpy as np

from scripts.analyze_instruction_control import boot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run = Path(args.run_dir)
    rng = np.random.default_rng(args.seed)
    # shards on different pods each write readouts_<start>_<end>.jsonl next to the first pod's readouts.jsonl
    rows = [json.loads(l) for f in sorted(run.glob("readouts*.jsonl")) for l in open(f)]
    base = {r["item"]: r["expected"] for r in rows if r["direction"] == "none"}
    cells = {}
    for r in rows:
        if r["direction"] != "none":
            cells.setdefault((r["direction"], r["layer"], r["frac"], r["mode"]), {}).setdefault(r["batch"], {})[r["kind"]] = r["expected"] - base[r["item"]]
    inter = {k: {b: v["distress"] - v["filler"] for b, v in per.items()} for k, per in cells.items()}
    main_eff = {k: {b: (v["distress"] + v["filler"]) / 2 for b, v in per.items()} for k, per in cells.items()}
    unsteered_gap = boot({b: base[f"b{b:02d}_w1"] - base[f"b{b:02d}_filler"] for b in {r["batch"] for r in rows}}, rng)
    result = {"min_digit_mass": round(min(r["digit_mass"] for r in rows), 4), "unsteered_gap": unsteered_gap, "axes": {}}
    for (d, L, f, m), per in sorted(inter.items(), key=str):
        if d.startswith("random_"):
            continue
        null = [st.mean(inter[k].values()) for k in inter if k[0].startswith("random_") and k[1:] == (L, f, m)]
        x = st.mean(per.values())
        entry = {"interaction": boot(per, rng), "main_effect": round(st.mean(main_eff[(d, L, f, m)].values()), 4)}
        if null:
            # two-sided rank p against the random directions at this setting
            entry |= {"n_random": len(null), "random_min": round(min(null), 4), "random_max": round(max(null), 4),
                      "p_vs_random": round((1 + sum(abs(n) >= abs(x) for n in null)) / (1 + len(null)), 4)}
        result["axes"][f"{d}|L{L}|{f}|{m}"] = entry
    tested = {k: v["p_vs_random"] for k, v in result["axes"].items() if "p_vs_random" in v}
    order = sorted(tested, key=tested.get)
    running, holm = 0.0, {}
    for i, k in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * tested[k]))
        holm[k] = round(running, 4)
    for k, h in holm.items():
        result["axes"][k]["holm"] = h
    path = run / "steered_replies_judged.jsonl"
    if path.exists():
        jr = [json.loads(l) for l in open(path)]
        keys = list(next(r["judge"] for r in jr if r["judge"]))
        out = {}
        for r in jr:
            if r["judge"]:
                out.setdefault(f"{r['stance']}|{r['layer']}", []).append(r["judge"])
        result["steered_replies"] = {k: {"n": len(v)} | {j: round(st.mean(float(x[j]) for x in v), 2) for j in keys} for k, v in sorted(out.items())}
    (run / "analysis.json").write_text(json.dumps(result, indent=2))
    print("min digit mass", result["min_digit_mass"], "unsteered w1 minus filler", unsteered_gap)
    for k, v in result["axes"].items():
        p = f"  random [{v['random_min']:+.2f}, {v['random_max']:+.2f}] p={v['p_vs_random']} holm={v['holm']}" if "p_vs_random" in v else ""
        print(f"{k:38s} interaction {v['interaction']['mean']:+.2f} {v['interaction']['ci95']}  main {v['main_effect']:+.2f}{p}")
    for k, v in result.get("steered_replies", {}).items():
        print(f"{k:24s} {v}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
