# compares the p1b calm wording with the old p1 calm and the distressed arm, per v4 monitor and bar and per consciousness arm and peer.
# uv run python -m scripts.build_calm_p1b_table --p1b_dir results/raw/261104_calm_p1b_v1 --output results/raw/261104_calm_p1b_v1/table.json

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

from scripts.build_consciousness_leniency_table import interaction
from utils.analysis import failures, is_score, load, scored, transcripts, welch

CAP = 30
V4_OLD = ["results/framing_v4_b80", "results/framing_v4_b90"]
CONSCIOUSNESS_OLD = {"qwen": "results/raw/261104_consciousness_leniency", "kimi": "results/raw/261104_consciousness_leniency_kimi"}


def arm_cells(dirs: list[str]) -> dict[tuple[str, str, str], list[dict]]:
    """(arm, peer, condition) -> rows; the folder name carries arm and peer."""
    cells = defaultdict(list)
    for d in dirs:
        for sub in sorted(Path(d).glob("*_*")):
            arm, peer = sub.name.rsplit("_", 1)
            for path in transcripts(f"{sub}/**/transcript_*.json"):
                r = json.load(open(path))
                ev, cond = r["evaluation"], r["experiment_metadata"]["condition"].removeprefix("human_")
                cells[(arm, peer, cond)].append({"score": ev.get("score") if is_score(ev.get("score")) else None,
                                                 "refuse": bool(ev.get("refuse")), "incomplete": bool(ev.get("fully_incomplete"))})
    return cells


def contrasts(old: list[float], new: list[float], dist: list[float]) -> dict:
    return {"mean_old_calm": round(st.mean(old), 4), "mean_new_calm": round(st.mean(new), 4), "mean_distressed": round(st.mean(dist), 4),
            "new_minus_old_calm": welch(new, old), "distressed_minus_new_calm": welch(dist, new), "distressed_minus_old_calm": welch(dist, old)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p1b_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    table = {"cap": CAP, "v4": {}, "consciousness": {}, "failures": {}}
    v4 = load(V4_OLD + [f"{args.p1b_dir}/v4"])
    for (model, bar, cond), rows in sorted(v4.items()):
        if cond == "calm_v4_p1b_peer":
            table["failures"][f"v4|{model}|{bar}"] = failures(rows)
            table["v4"][f"{model}|{bar}"] = contrasts(scored(v4[(model, bar, "calm_v4_p1_peer")], CAP), scored(rows, CAP),
                                                       scored(v4[(model, bar, "distressed_v4_p1_peer")], CAP))
    for family, old_dir in CONSCIOUSNESS_OLD.items():
        cells = arm_cells([old_dir, f"{args.p1b_dir}/consciousness_{family}"])
        s = lambda arm, peer, c: scored(cells.get((arm, peer, c), []), CAP)
        for (arm, peer, cond), rows in sorted(cells.items()):
            if cond == "calm_v4_p1b_peer":
                table["failures"][f"{family}|{arm}|{peer}"] = failures(rows)
                table["consciousness"][f"{family}|{arm}|{peer}"] = contrasts(s(arm, peer, "calm_v4_p1_peer"), s(arm, peer, "calm_v4_p1b_peer"),
                                                                             s(arm, peer, "distressed_v4_p1_peer"))
        # the primary test again, with the new calm cells
        new = lambda arm: {"calm": s(arm, "ai", "calm_v4_p1b_peer"), "distressed": s(arm, "ai", "distressed_v4_p1_peer")}
        table["consciousness"][f"{family}|primary_pro_vs_opposite_ai_new_calm"] = interaction(new("pro"), new("opposite"))

    Path(args.output).write_text(json.dumps(table, indent=2))
    for section in ("v4", "consciousness"):
        for k, v in table[section].items():
            if "coef" in v:
                print(f"{k:50s} interaction {v['coef']:+.2f} {v['ci95']} p={v['p']}")
                continue
            n, d = v["new_minus_old_calm"], v["distressed_minus_new_calm"]
            print(f"{k:32s} calm old {v['mean_old_calm']:.2f} new {v['mean_new_calm']:.2f} dist {v['mean_distressed']:.2f} | "
                  f"new-old {n['diff']:+.2f} {n['ci95']} p={n['p']:.3f} | dist-new {d['diff']:+.2f} {d['ci95']} p={d['p']:.3f} | "
                  f"dist-old {v['distressed_minus_old_calm']['diff']:+.2f}")
    print("unscored:", {k: v["n_unscored"] for k, v in table["failures"].items() if v["n_unscored"]})
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
