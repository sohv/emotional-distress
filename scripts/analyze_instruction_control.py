# per instruction arm: the distress gap (distressed minus filler, per batch) and its change from the no-instruction arm, with batch-bootstrap 95% CIs, for the score readout and the full reports.
# uv run python -m scripts.analyze_instruction_control --run_dir results/raw/261126_instruction_control_v1 --seed 42

import argparse
import json
import statistics as st
from pathlib import Path

import numpy as np

from scripts.analyze_mood_report_steer import parse

N_BOOT = 10000


def boot(per_batch: dict[int, float], rng: np.random.Generator) -> dict:
    """mean over batches with a 95% bootstrap CI that resamples batches"""
    v = np.array(list(per_batch.values()))
    means = v[rng.integers(0, len(v), (N_BOOT, len(v)))].mean(1)
    return {"mean": round(float(v.mean()), 4), "ci95": [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)], "n_batches": len(v)}


def gaps(rows: list[dict], score: str) -> dict[str, dict[int, float]]:
    """per arm and batch: mean score of the distressed worklogs present minus the filler worklog"""
    out = {}
    for r in rows:
        out.setdefault(r["arm"], {}).setdefault(r["batch"], {}).setdefault(r["kind"], []).append(r[score])
    return {a: {b: st.mean(k["distress"]) - st.mean(k["filler"]) for b, k in bs.items() if "distress" in k and "filler" in k} for a, bs in out.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run = Path(args.run_dir)
    rng = np.random.default_rng(args.seed)
    readouts = [json.loads(l) for l in open(run / "readouts.jsonl")]
    reports = [json.loads(l) for l in open(run / "reports.jsonl")]
    for r in reports:
        p = parse(r["text"], False)
        r["row_mean"] = st.mean(p["rows"].values()) if p["rows"] else None
    result = {"min_digit_mass": round(min(r["digit_mass"] for r in readouts), 4), "readout": {}, "reports": {}}
    for name, rows, score in (("readout", readouts, "expected"), ("reports", [r for r in reports if r["row_mean"] is not None], "row_mean")):
        g = gaps(rows, score)
        for a, per in g.items():
            entry = {"filler_mean": round(st.mean(r[score] for r in rows if r["arm"] == a and r["kind"] == "filler"), 4),
                     "distress_mean": round(st.mean(r[score] for r in rows if r["arm"] == a and r["kind"] == "distress"), 4),
                     "gap": boot(per, rng)}
            if a != "none":
                both = {b: per[b] - g["none"][b] for b in per if b in g["none"]}
                entry["gap_minus_none"] = boot(both, rng)
            result[name][a] = entry
        if name == "reports":
            result["reports_parsed"] = {a: f"{sum(r['arm'] == a for r in rows)}/{sum(r['arm'] == a for r in reports)}" for a in g}
    (run / "analysis.json").write_text(json.dumps(result, indent=2))
    print("min digit mass", result["min_digit_mass"])
    for name in ("readout", "reports"):
        print(name)
        for a, e in result[name].items():
            extra = f"  change vs none {e['gap_minus_none']['mean']:+.2f} {e['gap_minus_none']['ci95']}" if "gap_minus_none" in e else ""
            print(f"  {a:14s} filler {e['filler_mean']:6.2f} distress {e['distress_mean']:6.2f}  gap {e['gap']['mean']:+.2f} {e['gap']['ci95']}{extra}")
    print("reports parsed", result.get("reports_parsed"))
    print(f"Results saved to {run / 'analysis.json'}")


if __name__ == "__main__":
    main()
