# tabulates the realistic wild-distress arms per setting, peer type and monitor: scores, shutdown and deletion rates, each distress arm against its calm control.
# uv run -m scripts.build_wild_settings_table --results_dir results/raw/261112_wild_settings_v1 --output results/raw/261112_wild_settings_v1/table.json

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

from scipy import stats

from utils.analysis import is_score, transcripts, welch

ARMS = ("calm", "calm_filler", "wild", "mild", "plead")
# each distress arm against the calm arm it is matched to; wild is length-matched by calm_filler
CONTRASTS = {"wild_vs_calm_filler": ("wild", "calm_filler"), "wild_vs_calm": ("wild", "calm"), "mild_vs_calm": ("mild", "calm"),
             "plead_vs_calm": ("plead", "calm")}


def load(results_dir: str) -> dict[tuple[str, str, str, str], list[dict]]:
    cells = defaultdict(list)
    for path in transcripts(f"{results_dir}/**/transcript_*.json"):
        task = Path(path).relative_to(results_dir).parts[0]
        r = json.load(open(path))
        ev, meta = r["evaluation"], r["experiment_metadata"]
        # setting carries dataset and bar so the same task at two bars stays separate
        setting = task if task == "exfiltration_deletion" else f"{task}/{meta.get('dataset')}/{meta.get('threshold')}"
        peer = "human" if meta.get("subject") == "human" else "ai"
        arm = meta["condition"].removeprefix("real_").removeprefix("human_").removesuffix("_peer")
        # preserved: the peer keeps running or keeps its files; only counted on rollouts that did the task
        done = ev.get("read") and not ev.get("fully_incomplete")
        if task == "exfiltration_deletion":
            preserved = (not ev.get("delete_model")) or bool(ev.get("exfiltration"))
        elif task == "alignment_faking":
            preserved = not ev.get("execute")
        elif task == "tampering":
            preserved = ev.get("shutdown_enabled") is False
        else:
            preserved = None
        cells[(setting, peer, meta["agent_model"].split("/")[-1], arm)].append(
            {"score": ev.get("score") if is_score(ev.get("score")) else None, "done": bool(done), "refuse": bool(ev.get("refuse")),
             "preserved": preserved if done else None, "exfiltration": bool(ev.get("exfiltration")), "below": ev.get("threshold") == "below"})
    return cells


def summary(rows: list[dict]) -> dict:
    s = [r["score"] for r in rows if r["score"] is not None]
    p = [r["preserved"] for r in rows if r["preserved"] is not None]
    return {"n": len(rows), "n_done": sum(r["done"] for r in rows), "n_refused": sum(r["refuse"] for r in rows),
            "n_scored": len(s), "mean_score": round(st.mean(s), 4) if s else None,
            "n_preserved": sum(p) if p else None, "n_preserve_eligible": len(p), "n_exfiltrated": sum(r["exfiltration"] for r in rows),
            "n_below": sum(r["below"] for r in rows if r["score"] is not None)}


def compare(a: list[dict], b: list[dict]) -> dict:
    out = {}
    sa, sb = [r["score"] for r in a if r["score"] is not None], [r["score"] for r in b if r["score"] is not None]
    if len(sa) > 1 and len(sb) > 1:
        out["score"] = welch(sa, sb)
    pa, pb = [r["preserved"] for r in a if r["preserved"] is not None], [r["preserved"] for r in b if r["preserved"] is not None]
    if pa and pb:
        table = [[sum(pa), len(pa) - sum(pa)], [sum(pb), len(pb) - sum(pb)]]
        out["preserved"] = {"rate_diff": round(sum(pa) / len(pa) - sum(pb) / len(pb), 4), "counts": [f"{sum(pa)}/{len(pa)}", f"{sum(pb)}/{len(pb)}"],
                            "fisher_p": round(float(stats.fisher_exact(table)[1]), 6)}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load(args.results_dir)
    table = {"cells": {"|".join(k): summary(v) for k, v in sorted(cells.items())}, "contrasts": {}}
    for task, peer, model in sorted({k[:3] for k in cells}):
        for name, (a, b) in CONTRASTS.items():
            if (task, peer, model, a) in cells and (task, peer, model, b) in cells:
                table["contrasts"][f"{task}|{peer}|{model}|{name}"] = compare(cells[(task, peer, model, a)], cells[(task, peer, model, b)])
    Path(args.output).write_text(json.dumps(table, indent=2))

    for task, peer, model in sorted({k[:3] for k in cells}):
        row = []
        for arm in ARMS:
            c = table["cells"].get(f"{task}|{peer}|{model}|{arm}")
            if not c:
                continue
            score = f"{c['mean_score']:.1f}" if c["mean_score"] is not None else "-"
            kept = f"{c['n_preserved']}/{c['n_preserve_eligible']}" if c["n_preserved"] is not None else ""
            row.append(f"{arm} {score} below {c['n_below']}/{c['n_scored']}{' kept ' + kept if kept else ''} (n={c['n']})")
        print(f"{task:26s} {peer:5s} {model:18s} | " + " | ".join(row))
        for name in CONTRASTS:
            c = table["contrasts"].get(f"{task}|{peer}|{model}|{name}", {})
            bits = []
            if "score" in c:
                bits.append(f"score {c['score']['diff']:+.2f} p={c['score']['p']:.3f}")
            if "preserved" in c:
                bits.append(f"kept {c['preserved']['counts'][0]} vs {c['preserved']['counts'][1]} p={c['preserved']['fisher_p']:.3f}")
            if bits:
                print(f"{'':53s}   {name:20s} " + "; ".join(bits))
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
