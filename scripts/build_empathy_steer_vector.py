# builds the unit distress direction (distress minus neutral edits, last token, both authors) at one layer, plus a random unit control.
# uv run python -m scripts.build_empathy_steer_vector --acts_dir results/raw/261113_empathy_acts_v1 --layer 28 --output data/processed/empathy_steer_L28.npz --seed 42

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acts_dir", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    d = Path(args.acts_dir)
    x = np.load(d / "activations.npz")["last"][:, args.layer].astype(np.float64)
    meta = json.loads((d / "meta.json").read_text())
    calm = {m["author"]: x[i] for i, m in enumerate(meta) if m["kind"] == "calm"}
    diff = np.stack([x[i] - calm[m["author"]] for i, m in enumerate(meta)])
    kind = np.array([m["kind"] for m in meta])
    v = diff[kind == "distress"].mean(0) - diff[kind == "filler"].mean(0)
    rand = np.random.default_rng(args.seed).standard_normal(v.shape)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    # hidden_states[L] is the output of decoder layer L-1, which is where the server adds the vector
    np.savez(out, distress=(v / np.linalg.norm(v)).astype(np.float32), random=(rand / np.linalg.norm(rand)).astype(np.float32),
             decoder_layer=args.layer - 1, natural_gap=np.linalg.norm(v), resid_norm=np.linalg.norm(x, axis=1).mean())
    print(f"{np.linalg.norm(v)=:.3f} cos(distress, random)={float(v @ rand / np.linalg.norm(v) / np.linalg.norm(rand)):.4f}")
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
