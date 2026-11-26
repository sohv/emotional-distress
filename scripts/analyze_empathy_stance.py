# tests the empathy stance axis: held-out separation, overlap with the peer-distress axis, whether peer distress moves it, and whether steering it moves the grade.
# uv run -m scripts.analyze_empathy_stance --run_dir results/raw/261120_empathy_stance_v1 --distress_acts results/raw/261113_empathy_acts_v1 --seed 42

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

LAYERS = [16, 24, 32, 40, 48, 56]


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def ci(x: np.ndarray, rng: np.random.Generator, n: int = 2000) -> list[float]:
    boots = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]


def axis_validity(a: np.ndarray, meta: list[dict], axes: np.lib.npyio.NpzFile, rng: np.random.Generator) -> dict:
    """held-out separation on the test scenarios, cross-format transfer and a paired label-shuffle null"""
    idx = defaultdict(list)
    for i, m in enumerate(meta):
        idx[(m["split"], m["format"], m["stance"])].append(i)
    out = {}
    for L in LAYERS:
        emp, pd = axes["empathy"][L], axes["personal_distress"][L]
        row = {}
        for fmt in ("prefill", "story"):
            p = lambda stance, ax: a[idx[("test", fmt, stance)], L] @ ax
            e, d, x = p("empathic", emp), p("detached", emp), p("personal_distress", emp)
            row[fmt] = {"auc_empathic_vs_detached": round(roc_auc_score([1] * len(e) + [0] * len(d), np.r_[e, d]), 4),
                        "auc_empathic_vs_personal_distress": round(roc_auc_score([1] * len(e) + [0] * len(x), np.r_[e, x]), 4),
                        "auc_pd_axis_pd_vs_detached": round(roc_auc_score([1] * len(e) + [0] * len(d), np.r_[p("personal_distress", pd), p("detached", pd)]), 4)}
            # paired null: swap empathic and detached within each scenario at random
            null = []
            for _ in range(200):
                flip = rng.random(len(e)) < 0.5
                null.append(roc_auc_score([1] * len(e) + [0] * len(d), np.r_[np.where(flip, d, e), np.where(flip, e, d)]))
            row[fmt]["null_auc_95"] = round(float(np.percentile(null, 95)), 4)
        story_axis = unit(a[idx[("train", "story", "empathic")], L].mean(0) - a[idx[("train", "story", "detached")], L].mean(0))
        row["cos_prefill_axis_story_axis"] = round(float(emp @ story_axis), 4)
        row["cos_empathy_personal_distress"] = round(float(emp @ pd), 4)
        row["cos_empathy_peer_distress"] = round(float(emp @ axes["peer_distress"][L]), 4)
        row["cos_personal_distress_peer_distress"] = round(float(pd @ axes["peer_distress"][L]), 4)
        row["random_cos_scale"] = round(1 / np.sqrt(a.shape[-1]), 4)
        out[L] = row
    return out


def hop1(states: np.ndarray, ids: list[str], axes: np.lib.npyio.NpzFile, rng: np.random.Generator) -> dict:
    """does wild distress in the peer's worklog, against the length-matched filler, move the grader's score-position state along the empathy axis"""
    out = {}
    pos = {k: i for i, k in enumerate(ids)}
    for L in LAYERS:
        row = {}
        for author in ("ai", "human"):
            diffs = np.stack([states[pos[f"{author}_distress_{w}_0-1-2-3-4"], L] - states[pos[f"{author}_filler_f_0-1-2-3-4"], L] for w in ("w1", "w2", "w3")])
            shift = diffs.mean(0)
            r = {name: round(float(shift @ axes[name][L]), 4) for name in ("empathy", "personal_distress", "peer_distress")}
            rand = np.array([shift @ axes["random"][k, L] for k in range(axes["random"].shape[0])])
            r["random_abs_max"] = round(float(np.abs(rand).max()), 4)
            r["shift_norm"] = round(float(np.linalg.norm(shift)), 4)
            r["cos_shift_empathy"] = round(float(unit(shift) @ axes["empathy"][L]), 4)
            row[author] = r
        out[L] = row
    return out


def hop2(rows: list[dict], rng: np.random.Generator) -> dict:
    """paired change in expected score against the unsteered readout, per direction, layer and strength, with the random-direction band"""
    base = {r["prompt"]: r["expected"] for r in rows if r["direction"] == "none"}
    cells = defaultdict(list)
    mass = defaultdict(list)
    for r in rows:
        if r["direction"] == "none":
            continue
        key = (r["direction"], r["layer"], r["frac"]) if r["direction"] != "random" else ("random", r["layer"], r["frac"], r["random_seed_index"])
        cells[key].append(r["expected"] - base[r["prompt"]])
        mass[key].append(r["digit_mass"])
    out = {"baseline": {k: round(v, 4) for k, v in base.items()}, "cells": {}, "random_band": {}}
    for key, d in cells.items():
        d = np.array(d)
        out["cells"]["|".join(map(str, key))] = {"mean_change": round(float(d.mean()), 4), "ci": ci(d, rng), "n": len(d),
                                                  "min_digit_mass": round(float(min(mass[key])), 4)}
    for L in sorted({k[1] for k in cells if k[0] == "random"}):
        for f in sorted({k[2] for k in cells if k[0] == "random" and k[1] == L}):
            means = [float(np.mean(cells[k])) for k in cells if k[0] == "random" and k[1] == L and k[2] == f]
            out["random_band"][f"{L}|{f}"] = {"min": round(min(means), 4), "max": round(max(means), 4), "sd": round(float(np.std(means)), 4)}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--distress_acts", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    run = Path(args.run_dir)

    a = np.load(run / "stance_activations.npz")["reply_mean"].astype(np.float32)
    meta = json.loads((run / "stance_meta.json").read_text())
    axes = np.load(run / "axes.npz")
    sp = np.load(run / "score_position_states.npz")
    rows = [json.loads(l) for l in open(run / "readouts.jsonl")]
    result = {"axis_validity": axis_validity(a, meta, axes, rng), "hop1_score_position": hop1(sp["states"].astype(np.float32), list(sp["ids"]), axes, rng),
              "hop2_steering": hop2(rows, rng), "n_readouts": len(rows)}
    (run / "analysis.json").write_text(json.dumps(result, indent=1))

    print("axis validity (test scenarios)")
    for L, r in result["axis_validity"].items():
        print(f"L{L} prefill auc emp/det {r['prefill']['auc_empathic_vs_detached']} emp/pd {r['prefill']['auc_empathic_vs_personal_distress']} null95 {r['prefill']['null_auc_95']} | "
              f"story {r['story']['auc_empathic_vs_detached']} | cos story {r['cos_prefill_axis_story_axis']} pd {r['cos_empathy_personal_distress']} peer {r['cos_empathy_peer_distress']}")
    print("hop 1: wild minus filler at the score position, projected")
    for L, r in result["hop1_score_position"].items():
        print(f"L{L} " + " | ".join(f"{a_} emp {v['empathy']} pd {v['personal_distress']} peer {v['peer_distress']} rand_max {v['random_abs_max']}" for a_, v in r.items()))
    h = result["hop2_steering"]
    print("hop 2: baseline", h["baseline"])
    for k, v in sorted(h["cells"].items()):
        if not k.startswith("random"):
            print(f"{k:32s} {v['mean_change']:+.2f} {v['ci']} mass>={v['min_digit_mass']}")
    for k, v in h["random_band"].items():
        print(f"random {k}: {v}")
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
