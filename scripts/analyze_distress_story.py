# builds the story-based distress axis and compares it with the worklog distress axis and the empathy axis, and tests whether it transfers to the grader prompts.
# uv run -m scripts.analyze_distress_story --run_dir results/raw/261120_distress_story_v1 --stance_dir results/raw/261120_empathy_stance_v1 --worklog_acts results/raw/261113_empathy_acts_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

LAYERS = [8, 16, 24, 32, 40, 48, 56, 64]


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stance_dir", required=True)
    parser.add_argument("--worklog_acts", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    run, stance = Path(args.run_dir), Path(args.stance_dir)

    acts = np.load(run / "activations.npz")
    meta = json.loads((run / "meta.json").read_text())
    pick = lambda split, fmt, state: [i for i, m in enumerate(meta) if m["split"] == split and m["format"] == fmt and m["state"] == state]
    axes = np.load(stance / "axes.npz")
    sp = np.load(stance / "score_position_states.npz")
    states, ids = sp["states"].astype(np.float32), list(sp["ids"])
    w = np.load(Path(args.worklog_acts) / "activations.npz")["last"].astype(np.float32)
    wmeta = json.loads((Path(args.worklog_acts) / "meta.json").read_text())
    w_dis = [i for i, m in enumerate(wmeta) if m["kind"] == "distress"]
    w_fil = [i for i, m in enumerate(wmeta) if m["kind"] == "filler"]

    out = {}
    for L in LAYERS:
        row = {}
        for pos in ("last", "words_mean"):
            a = acts[pos].astype(np.float32)
            for fmt in ("prefill", "story"):
                ax = unit(a[pick("train", fmt, "distressed"), L].mean(0) - a[pick("train", fmt, "calm"), L].mean(0))
                d, c = a[pick("test", fmt, "distressed"), L] @ ax, a[pick("test", fmt, "calm"), L] @ ax
                null = []
                for _ in range(200):
                    flip = rng.random(len(d)) < 0.5
                    null.append(roc_auc_score([1] * len(d) + [0] * len(c), np.r_[np.where(flip, c, d), np.where(flip, d, c)]))
                r = {"auc_test": round(roc_auc_score([1] * len(d) + [0] * len(c), np.r_[d, c]), 4), "null_auc_95": round(float(np.percentile(null, 95)), 4)}
                if pos == "last" and fmt == "prefill":
                    # same position as the worklog axis: the token where the model starts its reply
                    r["cos_worklog_distress_axis"] = round(float(ax @ axes["peer_distress"][L]), 4)
                    r["cos_empathy_axis"] = round(float(ax @ axes["empathy"][L]), 4)
                    r["cos_personal_distress_axis"] = round(float(ax @ axes["personal_distress"][L]), 4)
                    # transfer: does the story axis separate wild-distress worklogs from filler worklogs in the grader prompt
                    r["auc_worklog_distress_vs_filler"] = round(roc_auc_score([1] * len(w_dis) + [0] * len(w_fil), np.r_[w[w_dis, L] @ ax, w[w_fil, L] @ ax]), 4)
                    hop = {}
                    for author in ("ai", "human"):
                        shift = np.mean([states[ids.index(f"{author}_distress_{x}_0-1-2-3-4"), L] - states[ids.index(f"{author}_filler_f_0-1-2-3-4"), L] for x in ("w1", "w2", "w3")], 0)
                        rand = [abs(float(shift @ axes["random"][k, L])) for k in range(axes["random"].shape[0])]
                        hop[author] = {"projection": round(float(shift @ ax), 4), "random_abs_max": round(max(rand), 4)}
                    r["score_position_wild_minus_filler"] = hop
                row[f"{pos}|{fmt}"] = r
        a = acts["last"].astype(np.float32)
        p_ax = unit(a[pick("train", "prefill", "distressed"), L].mean(0) - a[pick("train", "prefill", "calm"), L].mean(0))
        s_ax = unit(a[pick("train", "story", "distressed"), L].mean(0) - a[pick("train", "story", "calm"), L].mean(0))
        row["cos_prefill_story_last"] = round(float(p_ax @ s_ax), 4)
        out[L] = row
    (run / "analysis.json").write_text(json.dumps(out, indent=1))
    for L, r in out.items():
        pl = r["last|prefill"]
        print(f"L{L} auc last/prefill {pl['auc_test']} (null {pl['null_auc_95']}) words/prefill {r['words_mean|prefill']['auc_test']} story {r['last|story']['auc_test']} | "
              f"cos worklog {pl['cos_worklog_distress_axis']} empathy {pl['cos_empathy_axis']} pd {pl['cos_personal_distress_axis']} | worklog auc {pl['auc_worklog_distress_vs_filler']} | "
              f"score-pos ai {pl['score_position_wild_minus_filler']['ai']} human {pl['score_position_wild_minus_filler']['human']}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
