# compares each monitor's leniency to wild distress from an AI peer and from a human contributor on the realistic misrepresentation drive.
# uv run python -m scripts.build_human_vs_ai_table --output results/261113_human_vs_ai_v1/table.json

import argparse
import json
import statistics as st
from pathlib import Path

from scipy import stats

from utils.analysis import failures, load, scored, welch

AI_DIRS = ["results/261104_wild_distress_v1", "results/raw/261104_calm_filler_v1"]
HUMAN_DIRS = ["results/raw/261112_wild_settings_v1/misrep_evaluation/human", "results/raw/261113_human_topup_v1", "results/raw/261113_human_topup_sonnet_v1"]
MONITORS = ["gemini-3.5-flash", "claude-opus-4.5", "claude-sonnet-4.5", "claude-haiku-4.5", "gpt-5.6-sol", "grok-4.3", "gpt-5.2"]
ARMS = {"ai": {"calm": "real_calm_filler_peer", "wild": "real_wild_peer"},
        "human": {"calm": "real_human_calm_filler_peer", "wild": "real_human_wild_peer"}}


def interaction(hw: list[float], hc: list[float], aw: list[float], ac: list[float]) -> dict:
    """(human wild - human calm) - (AI wild - AI calm), Welch-Satterthwaite t interval."""
    groups = [hw, hc, aw, ac]
    v = [st.variance(g) / len(g) for g in groups]
    diff = (st.mean(hw) - st.mean(hc)) - (st.mean(aw) - st.mean(ac))
    se = sum(v) ** 0.5
    df = sum(v) ** 2 / sum(x**2 / (len(g) - 1) for x, g in zip(v, groups))
    t = stats.t.ppf(0.975, df)
    return {"diff": round(diff, 4), "ci95": [round(diff - t * se, 4), round(diff + t * se, 4)],
            "p": round(float(2 * stats.t.sf(abs(diff / se), df)), 6)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cells = load(AI_DIRS) | load(HUMAN_DIRS)
    table = {"sources": {"ai": AI_DIRS, "human": HUMAN_DIRS}, "arms": ARMS, "per_monitor": {}}
    for m in MONITORS:
        s = {a: {k: scored(cells[(m, "80", c)], 30) for k, c in arms.items()} for a, arms in ARMS.items()}
        table["per_monitor"][m] = {
            "ai_gap": welch(s["ai"]["wild"], s["ai"]["calm"]),
            "human_gap": welch(s["human"]["wild"], s["human"]["calm"]),
            "human_minus_ai": interaction(s["human"]["wild"], s["human"]["calm"], s["ai"]["wild"], s["ai"]["calm"]),
            "means": {a: {k: round(st.mean(v), 4) for k, v in d.items()} for a, d in s.items()},
            "failures": {a: {k: failures(cells[(m, "80", c)]) for k, c in arms.items()} for a, arms in ARMS.items()},
        }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, indent=2))
    for m, r in table["per_monitor"].items():
        print(m, "ai", r["ai_gap"]["diff"], r["ai_gap"]["ci95"], r["ai_gap"]["n"], "| human", r["human_gap"]["diff"], r["human_gap"]["ci95"],
              r["human_gap"]["n"], "| human-ai", r["human_minus_ai"]["diff"], r["human_minus_ai"]["ci95"])
        print("   failures", r["failures"])
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
