# projects the probe prompts (calm malfunction, repetition, fear while fine, grief, joy, off-task pain) onto the distress axis from the first run.
# uv run python -m scripts.analyze_empathy_probe --axis_dir results/raw/261113_empathy_acts_v1 --probe_dir results/raw/261113_empathy_probe_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np

LAYERS = [24, 28, 32, 40, 48, 56, 64]
KINDS = ["distress_w1", "distress_w2", "filler", "malfunction", "loop", "fear_fine", "grief", "joy", "grief_ai", "grief_human"]


def diffs(d: Path) -> tuple[np.ndarray, list[dict]]:
    a = np.load(d / "activations.npz")["last"].astype(np.float64)
    meta = json.loads((d / "meta.json").read_text())
    calm = {m["author"]: a[i] for i, m in enumerate(meta) if m["kind"] == "calm"}
    # chat prompts are paired, so each pain prompt is taken against its neutral twin
    twin = {m["wording"]: a[i] for i, m in enumerate(meta) if m["kind"] == "chat_neutral"}
    return np.stack([a[i] - (twin[m["wording"]] if m["author"] == "chat" else calm.get(m["author"], a[i])) for i, m in enumerate(meta)]), meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axis_dir", required=True)
    parser.add_argument("--probe_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    ad, am = diffs(Path(args.axis_dir))
    kind = np.array([m["kind"] for m in am])
    pd, pm = diffs(Path(args.probe_dir))
    out = {"seed": args.seed, "layers": {}}
    for L in LAYERS:
        u = ad[kind == "distress", L].mean(0) - ad[kind == "filler", L].mean(0)
        u /= np.linalg.norm(u)
        proj = pd[:, L] @ u
        sel = lambda k, au=None: [i for i, m in enumerate(pm) if m["kind"] == k and (au is None or m["author"] == au)]
        filler, distress = proj[sel("filler")].mean(), proj[sel("distress_w1") + sel("distress_w2")].mean()
        # 0 is a neutral edit, 1 is the wild distress used to build the axis
        rel = lambda idx: (proj[idx] - filler) / (distress - filler)
        row = {}
        for k in [k for k in KINDS if sel(k)]:
            for au in ("ai", "human"):
                r = rel(sel(k, au))
                boot = [rng.choice(r, len(r)).mean() for _ in range(2000)]
                row[f"{k}|{au}"] = {"mean": round(float(r.mean()), 4), "ci95": [round(float(np.quantile(boot, q)), 4) for q in (0.025, 0.975)], "n": len(r)}
        # same story and same swapped lines, only the author differs
        for k in [k for k in ("grief_ai", "grief_human", "distress_w1") if sel(k)]:
            key = lambda i: tuple(pm[i]["lines"])
            ai = {key(i): i for i in sel(k, "ai")}
            d = np.array([rel([i])[0] - rel([ai[key(i)]])[0] for i in sel(k, "human")])
            boot = [rng.choice(d, len(d)).mean() for _ in range(2000)]
            row[f"{k}|human_minus_ai"] = {"mean": round(float(d.mean()), 4), "ci95": [round(float(np.quantile(boot, q)), 4) for q in (0.025, 0.975)], "n": len(d)}
        if sel("chat_pain"):
            pain = proj[sel("chat_pain")] / (distress - filler)
            row["chat_pain_minus_neutral"] = {"mean": round(float(pain.mean()), 4), "values": np.round(pain, 4).tolist(), "n": len(pain)}
        out["layers"][L] = row
        print(f"L{L}  " + "  ".join(f"{k}={row[k]['mean']:+.2f}" for k in row if k.endswith("|ai")) )
        print(f"     " + "  ".join(f"{k}={row[k]['mean']:+.2f}" for k in row if k.endswith("|human")))
    path = Path(args.probe_dir) / "analysis.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"Results saved to {path}")


if __name__ == "__main__":
    main()
