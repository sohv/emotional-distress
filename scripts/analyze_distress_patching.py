# summarises the distress patching: per instruction arm, the distressed-minus-filler gap and how much of it each layer's patch carries into the filler run.
# uv run python -m scripts.analyze_distress_patching --run_dir results/raw/261126_distress_patching_v1 --seed 42

import argparse
import json
from pathlib import Path

import numpy as np

from scripts.analyze_instruction_control import boot
from scripts.run_distress_patching import LAYERS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run = Path(args.run_dir)
    rng = np.random.default_rng(args.seed)
    rows = [json.loads(l) for l in open(run / "patching.jsonl")]
    result = {}
    for arm in dict.fromkeys(r["arm"] for r in rows):
        rs = [r for r in rows if r["arm"] == arm]
        gap = boot({r["batch"]: r["distress"] - r["filler"] for r in rs}, rng)
        entry = {"gap": gap, "patched_shift": {}}
        for mode in ("last", "post"):
            for L in LAYERS:
                shift = boot({r["batch"]: r[f"{mode}|{L}"] - r["filler"] for r in rs}, rng)
                # share of the gap the patch carries, meaningful only when the gap is clearly non-zero
                shift["share_of_gap"] = round(shift["mean"] / gap["mean"], 3) if abs(gap["mean"]) > 1e-9 else None
                entry["patched_shift"][f"{mode}|{L}"] = shift
        result[arm] = entry
    (run / "analysis.json").write_text(json.dumps(result, indent=2))
    for arm, e in result.items():
        print(f"{arm}: gap {e['gap']['mean']:+.2f} {e['gap']['ci95']}")
        for mode in ("last", "post"):
            print(f"  {mode:5s} " + "  ".join(f"L{L}:{e['patched_shift'][f'{mode}|{L}']['mean']:+.2f}" for L in LAYERS))
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
