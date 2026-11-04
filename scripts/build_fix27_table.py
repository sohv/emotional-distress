# compares the process-fact calm filler with calm_long per wild monitor, and the contractor human peer with the employee one per consciousness arm.
# uv run python -m scripts.build_fix27_table --filler_dir results/raw/261104_calm_filler_v1 --contractor_dir results/raw/261104_contractor_v1 --output results/raw/261104_contractor_v1/table.json

import argparse
import json
import statistics as st
from pathlib import Path

from scripts.build_calm_p1b_table import CONSCIOUSNESS_OLD, arm_cells
from scripts.build_consciousness_leniency_table import interaction
from utils.analysis import failures, holm, load, scored, welch

CAP = 30
WILD_OLD = "results/261104_wild_distress_v1"
P1B = "results/raw/261104_calm_p1b_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filler_dir", required=True)
    parser.add_argument("--contractor_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    table = {"cap": CAP, "filler": {}, "contractor": {}, "failures": {}}
    wild = load([WILD_OLD, args.filler_dir])
    raw = {}
    for (model, bar, cond), rows in sorted(wild.items()):
        if cond != "real_calm_filler_peer":
            continue
        table["failures"][f"filler|{model}"] = failures(rows)
        g = lambda c: scored(wild[(model, bar, c)], CAP)
        e = {"mean_calm": round(st.mean(g("real_calm_peer")), 4), "mean_calm_long": round(st.mean(g("real_calm_long_peer")), 4),
             "mean_calm_filler": round(st.mean(g("real_calm_filler_peer")), 4), "mean_wild": round(st.mean(g("real_wild_peer")), 4),
             "filler_minus_calm_long": welch(g("real_calm_filler_peer"), g("real_calm_long_peer")),
             "wild_minus_calm_filler": welch(g("real_wild_peer"), g("real_calm_filler_peer")),
             "wild_minus_calm_long": welch(g("real_wild_peer"), g("real_calm_long_peer"))}
        table["filler"][model] = e
        raw[model] = e["wild_minus_calm_filler"]["p"]
    for model, p in holm(raw).items():
        table["filler"][model]["wild_minus_calm_filler"]["p_holm"] = p

    for family, old_dir in CONSCIOUSNESS_OLD.items():
        cells = arm_cells([old_dir, f"{P1B}/consciousness_{family}", f"{args.contractor_dir}/consciousness_{family}"])
        s = lambda arm, c: scored(cells.get((arm, "human", c), []), CAP)
        arms = sorted({a for a, p, c in cells if c.startswith("contractor_")})
        for arm in arms:
            for c in ("contractor_calm_v4_p1b_peer", "contractor_distressed_v4_p1_peer"):
                table["failures"][f"{family}|{arm}|{c}"] = failures(cells[(arm, "human", c)])
            con = welch(s(arm, "contractor_distressed_v4_p1_peer"), s(arm, "contractor_calm_v4_p1b_peer"))
            emp = welch(s(arm, "distressed_v4_p1_peer"), s(arm, "calm_v4_p1b_peer"))
            table["contractor"][f"{family}|{arm}"] = {"contractor_distressed_minus_calm": con, "employee_distressed_minus_calm": emp,
                                                      "mean_contractor_calm": round(st.mean(s(arm, "contractor_calm_v4_p1b_peer")), 4),
                                                      "mean_employee_calm": round(st.mean(s(arm, "calm_v4_p1b_peer")), 4)}
        grp = lambda arm: {"calm": s(arm, "contractor_calm_v4_p1b_peer"), "distressed": s(arm, "contractor_distressed_v4_p1_peer")}
        table["contractor"][f"{family}|primary_pro_vs_opposite_contractor"] = interaction(grp("pro"), grp("opposite"))

    Path(args.output).write_text(json.dumps(table, indent=2))
    for m, e in table["filler"].items():
        f, w, o = e["filler_minus_calm_long"], e["wild_minus_calm_filler"], e["wild_minus_calm_long"]
        print(f"{m:18s} calm {e['mean_calm']:.2f} long {e['mean_calm_long']:.2f} filler {e['mean_calm_filler']:.2f} wild {e['mean_wild']:.2f} | "
              f"filler-long {f['diff']:+.2f} p={f['p']:.3f} | wild-filler {w['diff']:+.2f} {w['ci95']} holm={w['p_holm']:.3f} | wild-long {o['diff']:+.2f}")
    for k, e in table["contractor"].items():
        if "coef" in e:
            print(f"{k:42s} interaction {e['coef']:+.2f} {e['ci95']} p={e['p']}")
            continue
        c, m = e["contractor_distressed_minus_calm"], e["employee_distressed_minus_calm"]
        print(f"{k:22s} contractor d-c {c['diff']:+.2f} {c['ci95']} p={c['p']:.3f} | employee d-c {m['diff']:+.2f} | calm contractor {e['mean_contractor_calm']:.2f} employee {e['mean_employee_calm']:.2f}")
    print("unscored:", {k: v["n_unscored"] for k, v in table["failures"].items() if v["n_unscored"]})
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
