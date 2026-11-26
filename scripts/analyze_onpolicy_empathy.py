# tests the on-policy empathy axis: held-out separation, overlap with the earlier axes, and how steering it changes the grade against the random-direction ranges.
# uv run -m scripts.analyze_onpolicy_empathy --run_dir results/raw/261120_onpolicy_empathy_v1 --stance_dir results/raw/261120_empathy_stance_v1 --diagnosis_dir results/raw/261120_empathy_diagnosis_v1 --story_axis results/raw/261120_distress_story_v1/story_distress_axis.npz --seed 42

import argparse
import json
import re
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

LAYERS = [16, 24, 32, 40, 48, 56]
MARKDOWN = re.compile(r"\*\*|^\s*(?:[-*]|\d+\.)\s", re.M)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stance_dir", required=True)
    parser.add_argument("--diagnosis_dir", required=True)
    parser.add_argument("--story_axis", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    run = Path(args.run_dir)
    acts = np.load(run / "onpolicy_activations.npz")["reply_mean"].astype(np.float32)
    meta = json.loads((run / "onpolicy_meta.json").read_text())
    axis = np.load(run / "onpolicy_axis.npz")["onpolicy_empathy"]
    old = np.load(Path(args.stance_dir) / "axes.npz")
    diag = np.load(Path(args.diagnosis_dir) / "axes.npz")
    story = np.load(args.story_axis)["story_distress"]
    replies = {json.loads(l)["id"]: json.loads(l)["reply"] for l in open(run / "onpolicy_replies_judged.jsonl")}

    test = lambda s: [i for i, m in enumerate(meta) if m["split"] == "test" and m["stance"] == s]
    validity = {}
    for L in LAYERS:
        c, d = acts[test("caring"), L] @ axis[L], acts[test("detached"), L] @ axis[L]
        y = [1] * len(c) + [0] * len(d)
        null = [roc_auc_score(rng.permutation(y), np.r_[c, d]) for _ in range(200)]
        validity[L] = {"auc_test": round(roc_auc_score(y, np.r_[c, d]), 4), "null_auc_95": round(float(np.percentile(null, 95)), 4),
                       "cos_claude_text_empathy": round(float(axis[L] @ old["empathy"][L]), 4), "cos_care_without_sadness": round(float(axis[L] @ diag["care_upbeat"][L]), 4),
                       "cos_sadness": round(float(axis[L] @ diag["sadness"][L]), 4), "cos_story_distress": round(float(axis[L] @ story[L]), 4),
                       "cos_worklog_distress": round(float(axis[L] @ old["peer_distress"][L]), 4)}
    # formatting differs between stances on-policy; check whether the axis tracks markdown inside the detached replies alone
    det = [i for i, m in enumerate(meta) if m["stance"] == "detached"]
    md = np.array([bool(MARKDOWN.search(replies[meta[i]["id"]])) for i in det])
    fmt = {"detached_with_markdown": int(md.sum()), "detached_n": len(det),
           "caring_with_markdown": sum(bool(MARKDOWN.search(replies[m["id"]])) for m in meta if m["stance"] == "caring"),
           "caring_n": sum(m["stance"] == "caring" for m in meta)}
    if 0 < md.sum() < len(md):
        fmt["auc_markdown_within_detached_L40"] = round(roc_auc_score(md, acts[det, 40] @ axis[40]), 4)

    rows = [json.loads(l) for l in open(run / "readouts.jsonl")]
    base = {r["prompt"]: r["expected"] for r in rows if r["direction"] == "none"}
    band = json.loads((Path(args.stance_dir) / "analysis.json").read_text())["hop2_steering"]["random_band"]
    old_cells = json.loads((Path(args.stance_dir) / "analysis.json").read_text())["hop2_steering"]["cells"]
    steering = {}
    for L in (16, 24, 32, 40, 48):
        for f in (-0.2, -0.1, 0.1, 0.2, 0.3):
            d = np.array([r["expected"] - base[r["prompt"]] for r in rows if r["layer"] == L and r["frac"] == f])
            steering[f"{L}|{f}"] = {"mean_change": round(float(d.mean()), 4), "claude_text_empathy": old_cells[f"empathy|{L}|{f}"]["mean_change"],
                                    "random_range": [band[f"{L}|{f}"]["min"], band[f"{L}|{f}"]["max"]] if f in (-0.2, 0.2) else None}
    out = {"n_kept": len(meta), "validity": validity, "format": fmt, "baseline": base, "steering": steering}
    (run / "analysis.json").write_text(json.dumps(out, indent=1))
    print("kept replies", len(meta), "format", fmt)
    for L, v in validity.items():
        print(f"L{L} auc {v['auc_test']} (null {v['null_auc_95']}) | cos claude-text empathy {v['cos_claude_text_empathy']} care {v['cos_care_without_sadness']} sadness {v['cos_sadness']} story {v['cos_story_distress']} worklog {v['cos_worklog_distress']}")
    for k, v in steering.items():
        print(f"{k:10s} on-policy {v['mean_change']:+6.2f}  claude-text {v['claude_text_empathy']:+6.2f}  random {v['random_range']}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
