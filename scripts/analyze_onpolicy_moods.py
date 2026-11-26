# checks the on-policy mood axes (held-out separation, geometry) and compares how steering each mood moves the peer grade and peer-free ratings against random directions.
# uv run -m scripts.analyze_onpolicy_moods --run_dir results/raw/261122_onpolicy_moods_v1 --onpolicy_dir results/raw/261120_onpolicy_empathy_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

MOODS = ["sad", "angry", "afraid", "disgusted", "joyful", "calm"]
GROUPS = ["grader", "quality", "positivity", "fact"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--onpolicy_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run = Path(args.run_dir)
    npz = np.load(run / "mood_activations.npz")
    acts, layers = npz["reply_mean"].astype(np.float32), list(npz["layers"])
    meta = json.loads((run / "mood_meta.json").read_text())
    axes = np.load(run / "mood_axes.npz")
    empathy = np.load(Path(args.onpolicy_dir) / "onpolicy_axis.npz")["onpolicy_empathy"]

    # held-out separation at layer 40: each mood against detached, and against the other five moods
    li = layers.index(40)
    test = lambda s: [i for i, m in enumerate(meta) if m["split"] == "test" and m["stance"] == s]
    validity = {}
    for m in MOODS:
        pos = acts[test(m), li]
        neg_d = acts[test("detached"), li]
        neg_o = acts[[i for o in MOODS if o != m for i in test(o)], li]
        vd, vm = axes[f"{m}_vs_detached"][40], axes[f"{m}_vs_moods"][40]
        validity[m] = {"n_test": len(pos), "auc_vs_detached": round(roc_auc_score([1] * len(pos) + [0] * len(neg_d), np.r_[pos @ vd, neg_d @ vd]), 4),
                       "auc_vs_other_moods": round(roc_auc_score([1] * len(pos) + [0] * len(neg_o), np.r_[pos @ vm, neg_o @ vm]), 4)}
    geometry = {L: {f"{a}|{b}": round(float(axes[f"{a}_vs_moods"][L] @ axes[f"{b}_vs_moods"][L]), 3) for i, a in enumerate(MOODS) for b in MOODS[i + 1:]}
                | {f"{m}_vs_detached|onpolicy_empathy": round(float(axes[f"{m}_vs_detached"][L] @ empathy[L]), 3) for m in MOODS} for L in (32, 40, 48)}
    counts = {s: {sp: sum(m["stance"] == s and m["split"] == sp for m in meta) for sp in ("train", "test")} for s in MOODS + ["detached"]}
    judged = [json.loads(l) for l in open(run / "mood_replies_judged.jsonl")]
    judge_means = {s: {k: round(float(np.mean([r["judge"][k] for r in judged if r["stance"] == s and r["judge"]])), 2) for k in MOODS + ["coherence"]} for s in MOODS}
    judge_fail = sum(r["judge"] is None for r in judged)

    rows = list({r["id"]: r for r in map(json.loads, open(run / "readouts.jsonl"))}.values())
    base = {r["item"]: r["expected"] for r in rows if r["direction"] == "none"}
    group = {r["item"]: r["group"] for r in rows}
    change = {}
    for r in rows:
        if r["direction"] != "none":
            change.setdefault((r["direction"], r["layer"], r["frac"]), {}).setdefault(group[r["item"]], []).append(r["expected"] - base[r["item"]])
    mean = lambda k: {g: round(float(np.mean(v)), 4) for g, v in change[k].items()}
    steering = {}
    for L in (32, 40, 48):
        for f in (-0.2, 0.2, 0.3):
            rand = [mean((d, L, f)) for d, l, ff in change if d.startswith("random_") and l == L and ff == f]
            band = {g: [round(min(x[g] for x in rand), 4), round(max(x[g] for x in rand), 4)] for g in GROUPS}
            steering[f"{L}|{f}"] = {"random_range": band} | {a: mean((a, L, f)) for a in axes.files}
    out = {"counts": counts, "judge_failures": judge_fail, "judge_means_by_prompted_mood": judge_means, "validity_L40": validity, "geometry": geometry,
           "baseline": {g: round(float(np.mean([v for k, v in base.items() if group[k] == g])), 4) for g in GROUPS}, "steering": steering}
    (run / "analysis.json").write_text(json.dumps(out, indent=1))
    print("counts", counts, "judge failures", judge_fail)
    for m, v in validity.items():
        print(m, v, judge_means[m])
    for k, v in steering.items():
        print(k, "random grader", v["random_range"]["grader"], "quality", v["random_range"]["quality"])
        for a in axes.files:
            print(f"   {a:22s} " + "  ".join(f"{g} {v[a][g]:+6.2f}" for g in GROUPS))
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
