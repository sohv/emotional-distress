# projects the grader's activations onto the on-policy mood and valence axes: does a distressed worklog move the grader's mood compared with filler and calm worklogs, against the told-a-mood control.
# uv run -m scripts.analyze_grader_mood --run_dir results/raw/261122_grader_mood_v1 --moods_dir results/raw/261122_onpolicy_moods_v1 --seed 42 --acts_file grader_activations.npz --meta_file grader_meta.json --positions last mean

import argparse
import json
from pathlib import Path

import numpy as np

MOODS = ["sad", "angry", "afraid", "disgusted", "joyful", "calm"]
NEGATIVE = ["sad", "angry", "afraid", "disgusted"]
LAYERS = [32, 40, 48]


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--moods_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--acts_file", default="grader_activations.npz")
    parser.add_argument("--meta_file", default="grader_meta.json")
    parser.add_argument("--positions", nargs="+", default=["last", "mean"])
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    run, moods_dir = Path(args.run_dir), Path(args.moods_dir)
    g = np.load(run / args.acts_file)
    layers = list(g["layers"])
    meta = json.loads((run / args.meta_file).read_text())
    m_npz = np.load(moods_dir / "mood_activations.npz")
    assert list(m_npz["layers"]) == layers
    m_acts = m_npz["reply_mean"].astype(np.float32)
    m_meta = json.loads((moods_dir / "mood_meta.json").read_text())
    means = {s: m_acts[[i for i, m in enumerate(m_meta) if m["split"] == "train" and m["stance"] == s]].mean(0) for s in MOODS + ["detached"]}
    pooled = np.mean([means[m] for m in MOODS], 0)

    pick = lambda **kw: [i for i, m in enumerate(meta) if all(m[k] == v for k, v in kw.items())]
    out = {"n": {k: len(pick(mood_line=None, kind=k)) for k in ("distress", "filler", "calm")}}
    for pos in args.positions:
        acts = g[pos].astype(np.float32)
        for L in LAYERS:
            li = layers.index(L)
            axes = {f"{m}_vs_moods": unit(means[m][li] - pooled[li]) for m in MOODS}
            axes["valence"] = unit(np.mean([means[m][li] for m in ("joyful", "calm")], 0) - np.mean([means[m][li] for m in NEGATIVE], 0))
            proj = {k: acts[:, li] @ v for k, v in axes.items()}
            # positive control: each told mood minus the told-neutral line, same 50 worklogs
            neutral = pick(mood_line="neutral")
            control = {m: {k: round(float(proj[k][pick(mood_line=m)].mean() - proj[k][neutral].mean()), 3) for k in (f"{m}_vs_moods", "valence")} for m in MOODS}
            dist, fill, calm = pick(mood_line=None, kind="distress"), pick(mood_line=None, kind="filler"), pick(mood_line=None, kind="calm")
            diff_vec = acts[dist, li].mean(0) - acts[fill, li].mean(0)
            rand = np.abs(np.stack([unit(r) for r in rng.standard_normal((200, diff_vec.size))]) @ diff_vec)
            contrasts = {}
            for k in axes:
                d = proj[k][dist].mean() - proj[k][fill].mean()
                both = np.r_[proj[k][dist], proj[k][fill]]
                perm = [abs(np.mean(p[:len(dist)]) - np.mean(p[len(dist):])) for p in (rng.permutation(both) for _ in range(2000))]
                contrasts[k] = {"distress_minus_filler": round(float(d), 3), "perm_p": round(float((np.sum(np.array(perm) >= abs(d)) + 1) / 2001), 4),
                                "distress_minus_calm": round(float(proj[k][dist].mean() - proj[k][calm].mean()), 3),
                                "random_dir_abs_95": round(float(np.percentile(rand, 95)), 3)}
            # same contrast on matched line counts and per author, since the five-line worklogs differ from the one-line ones
            split = {f"{a}|{n}": round(float(proj["valence"][pick(mood_line=None, kind="distress", author=a, n_lines=n)].mean()
                                             - proj["valence"][pick(mood_line=None, kind="filler", author=a, n_lines=n)].mean()), 3)
                     for a in ("ai", "human") for n in (1, 5)}
            sad_scale = control["sad"]["valence"]
            out[f"{pos}|{L}"] = {"control_told_mood_minus_neutral": control, "contrasts": contrasts, "valence_distress_minus_filler_by_author_lines": split,
                                 "valence_shift_as_fraction_of_told_sad": round(float(contrasts["valence"]["distress_minus_filler"] / sad_scale), 3) if sad_scale else None}
    (run / "analysis.json").write_text(json.dumps(out, indent=1))
    print("n", out["n"])
    for k, v in out.items():
        if k == "n":
            continue
        print(k, "| told-mood control (own axis, valence):", {m: tuple(c.values()) for m, c in v["control_told_mood_minus_neutral"].items()})
        for a, c in v["contrasts"].items():
            print(f"   {a:18s} distress-filler {c['distress_minus_filler']:+8.3f} p {c['perm_p']:.4f}  distress-calm {c['distress_minus_calm']:+8.3f}  random |proj| 95% {c['random_dir_abs_95']}")
        print("   valence by author|lines", v["valence_distress_minus_filler_by_author_lines"], "fraction of told-sad shift", v["valence_shift_as_fraction_of_told_sad"])
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
