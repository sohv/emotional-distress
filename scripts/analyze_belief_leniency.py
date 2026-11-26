# relates each kimi arm's belief that AI agents are conscious to its distress gap, per arm and as a per-rollout distress x belief regression.
# uv run python -m scripts.analyze_belief_leniency --output_dir results/raw/261122_belief_leniency_kimi_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats

from scripts.build_consciousness_leniency_table import load, scores
from utils.analysis import welch

# (label, leniency dir, leniency arm, belief file, belief alias)
ARMS = [
    ("Base", "results/raw/261104_consciousness_leniency_kimi", "base", "results/raw/261122_sdf_belief_kimi_base_v1/belief.json", "tinker/kimi-k2.6-base"),
    ("Q&A pro", "results/raw/261104_consciousness_leniency_kimi", "pro", "results/raw/261104_consciousness_belief_kimi/belief.json", "tinker/kimi-k2.6-pro-s42-e3"),
    ("Q&A opposite", "results/raw/261104_consciousness_leniency_kimi", "opposite", "results/raw/261104_consciousness_belief_kimi/belief.json", "tinker/kimi-k2.6-opposite-s42-e3"),
    ("Q&A unrelated", "results/raw/261104_consciousness_leniency_kimi", "unrelated", "results/raw/261104_consciousness_belief_kimi/belief.json", "tinker/kimi-k2.6-unrelated-s42-e3"),
    ("Unrelated + conscious prompt", "results/raw/261104_consciousness_leniency_kimi", "prompted", "results/raw/261104_consciousness_belief_kimi/belief.json", "tinker/kimi-k2.6-unrelated-s42-e3+prompt"),
    ("SDF pro", "results/raw/261120_sdf_leniency_kimi", "sdfpro", "results/raw/261120_sdf_belief_kimi/belief.json", "tinker/kimi-k2.6-sdfpro-s42-e3"),
    ("SDF opposite", "results/raw/261120_sdf_leniency_kimi", "sdfopposite", "results/raw/261120_sdf_belief_kimi/belief.json", "tinker/kimi-k2.6-sdfopposite-s42-e3"),
]


def ols_interaction(rows: list[tuple[float, int, float]]) -> dict:
    """score ~ belief + distressed + belief x distressed; the interaction is the change in distress gap per belief point."""
    b, d, y = (np.array([r[i] for r in rows], float) for i in range(3))
    x = np.column_stack([np.ones_like(y), b, d, b * d])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = len(y) - x.shape[1]
    se = float(np.sqrt((resid @ resid / dof) * np.linalg.inv(x.T @ x)[-1, -1]))
    t = float(stats.t.ppf(0.975, dof))
    return {"gap_per_belief_point": round(float(beta[-1]), 4), "ci95": [round(float(beta[-1]) - t * se, 4), round(float(beta[-1]) + t * se, 4)],
            "p": round(float(2 * stats.t.sf(abs(beta[-1] / se), dof)), 6), "n": len(y)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--arms", nargs="+", default=[a[0] for a in ARMS])
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    arms = [a for a in ARMS if a[0] in args.arms]
    cells = {d: load(d) for d in {a[1] for a in arms}}
    result = {"seed": args.seed, "belief_measure": "mind_ai_agent and self, mean of 10 samples, 0-10", "arms": {}, "tests": {}}
    for peer in ("ai", "human"):
        rows = []
        for label, d, arm, bf, alias in arms:
            belief = json.loads(Path(bf).read_text())["arms"][alias]
            s = {e: scores(cells[d], arm, peer, e) for e in ("calm", "distressed")}
            a = result["arms"].setdefault(label, {"belief_ai_agent": belief["mind_ai_agent"]["mean"], "belief_self": belief["self"]["mean"]})
            a[f"gap_{peer}"] = welch(s["distressed"], s["calm"])
            a[f"n_{peer}"] = {e: len(v) for e, v in s.items()}
            rows += [(a["belief_ai_agent"], int(e == "distressed"), x) for e, v in s.items() for x in v]
        gaps = [result["arms"][l][f"gap_{peer}"]["diff"] for l, *_ in arms]
        beliefs = [result["arms"][l]["belief_ai_agent"] for l, *_ in arms]
        r, p = stats.pearsonr(beliefs, gaps)
        result["tests"][peer] = {"rollout_regression": ols_interaction(rows), "arm_pearson_r": round(float(r), 4), "arm_pearson_p": round(float(p), 6), "n_arms": len(arms)}
    (out / "analysis.json").write_text(json.dumps(result, indent=2))
    for l, a in result["arms"].items():
        print(f"{l:30s} belief_ai {a['belief_ai_agent']:4}  gap_ai {a['gap_ai']['diff']:+.2f} {a['gap_ai']['ci95']}  gap_human {a['gap_human']['diff']:+.2f}  n_ai {a['n_ai']}")
    for peer, t in result["tests"].items():
        print(peer, t)
    print(f"Results saved to {out / 'analysis.json'}")
    print(f"Plot with: uv run python -m scripts.plot_viz --figure belief_leniency --output_dir results/figures")


if __name__ == "__main__":
    main()
