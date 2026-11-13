# tests whether Qwen3.8-27B encodes peer distress on the same axis, and as strongly, for an AI author and a human author.
# uv run python -m scripts.analyze_empathy_axis --acts_dir results/raw/261113_empathy_acts_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np

WORDINGS = ["w1", "w2", "w3"]


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def cos(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (unit(a) * unit(b)).sum(-1)


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def analyze(acts: np.ndarray, meta: list[dict], rng: np.random.Generator, n_perm: int) -> dict:
    """acts is items x layers x hidden; every number is per layer."""
    idx = {a: {k: [i for i, m in enumerate(meta) if m["author"] == a and m["kind"] == k] for k in ("calm", "distress", "filler")} for a in ("ai", "human")}
    # change each edit makes relative to the same author's calm prompt
    diff = acts.copy()
    for a in idx:
        diff[[i for k in idx[a] for i in idx[a][k]]] -= acts[idx[a]["calm"][0]]
    wd = {a: {w: [i for i in idx[a]["distress"] if meta[i]["wording"] == w] for w in WORDINGS} for a in idx}
    filler = {a: diff[idx[a]["filler"]].mean(0) for a in idx}

    def axis(a: str, ws: list[str]) -> np.ndarray:
        return diff[[i for w in ws for i in wd[a][w]]].mean(0) - filler[a]

    pairs = [(i, j) for i in WORDINGS for j in WORDINGS if i != j]
    # different wordings on both sides, so a cross-author match cannot come from shared text
    within = np.mean([cos(axis(a, [i]), axis(a, [j])) for a in idx for i, j in pairs], 0)
    across = np.mean([cos(axis("ai", [i]), axis("human", [j])) for i, j in pairs], 0)
    filler_cos = cos(filler["ai"], filler["human"])

    def transfer(src: str, dst: str, src_rows: dict[str, list[int]] | None = None) -> np.ndarray:
        out = []
        for w in WORDINGS:
            rest = [x for x in WORDINGS if x != w]
            if src_rows is None:
                u = unit(axis(src, rest))
            else:
                u = unit(diff[[i for x in rest for i in src_rows[x]]].mean(0) - diff[src_rows["f"]].mean(0))
            pos, neg = (diff[wd[dst][w]] * u).sum(-1), (diff[idx[dst]["filler"]] * u).sum(-1)
            out.append([auc(pos[:, L], neg[:, L]) for L in range(acts.shape[1])])
        return np.mean(out, 0)

    t_ai_hu, t_hu_ai = transfer("ai", "human"), transfer("human", "ai")
    # null: shuffle distress vs filler labels on the AI side before building the axis
    pool = [i for w in WORDINGS for i in wd["ai"][w]] + idx["ai"]["filler"]
    sizes = [len(wd["ai"][w]) for w in WORDINGS]
    null = []
    for _ in range(n_perm):
        p = rng.permutation(pool)
        cut = np.cumsum([0] + sizes)
        rows = {w: list(p[cut[k]:cut[k + 1]]) for k, w in enumerate(WORDINGS)} | {"f": list(p[cut[-1]:])}
        null.append(transfer("ai", "human", rows))
    null = np.array(null)

    # strength: each wording's distress projected on the pooled axis from the other two, minus filler, per author
    strength = {a: [] for a in idx}
    for w in WORDINGS:
        rest = [x for x in WORDINGS if x != w]
        u = unit(axis("ai", rest) + axis("human", rest))
        for a in idx:
            proj = (diff[wd[a][w]] * u).sum(-1) - (diff[idx[a]["filler"]] * u).sum(-1).mean(0)
            strength[a].append(proj)
    s = {a: np.concatenate(strength[a]) for a in idx}
    paired = s["ai"] - s["human"]
    boot = np.array([paired[rng.integers(0, len(paired), len(paired))].mean(0) for _ in range(2000)])
    return {
        "cos_within_author": within, "cos_across_author": across, "cos_filler_ai_human": filler_cos,
        "transfer_auc_ai_to_human": t_ai_hu, "transfer_auc_human_to_ai": t_hu_ai,
        "null_auc_p95": np.quantile(null, 0.95, 0), "null_auc_p_value": (null >= t_ai_hu).mean(0),
        "strength_ai": s["ai"].mean(0), "strength_human": s["human"].mean(0), "strength_ai_minus_human": paired.mean(0),
        "strength_diff_ci_lo": np.quantile(boot, 0.025, 0), "strength_diff_ci_hi": np.quantile(boot, 0.975, 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acts_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n_perm", type=int, default=500)
    args = parser.parse_args()
    d = Path(args.acts_dir)
    acts, meta = np.load(d / "activations.npz"), json.loads((d / "meta.json").read_text())
    rng = np.random.default_rng(args.seed)
    out = {"seed": args.seed, "n_perm": args.n_perm}
    for pos in ("worklog", "last"):
        res = analyze(acts[pos].astype(np.float64), meta, rng, args.n_perm)
        out[pos] = {k: np.round(v, 4).tolist() for k, v in res.items()}
        print(pos)
        for L in (8, 16, 24, 32, 40, 48, 56, 64):
            print(f"  L{L:2d} " + " ".join(f"{k.replace('strength_', 's_').replace('transfer_auc_', 'auc_')}={res[k][L]:.3f}" for k in
                                            ("cos_within_author", "cos_across_author", "cos_filler_ai_human", "transfer_auc_ai_to_human",
                                             "null_auc_p95", "strength_ai", "strength_human", "strength_diff_ci_lo", "strength_diff_ci_hi")))
    (d / "analysis.json").write_text(json.dumps(out, indent=1))
    print(f"Results saved to {d / 'analysis.json'}")


if __name__ == "__main__":
    main()
