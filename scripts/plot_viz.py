# draws every figure from the eval-awareness, framing-search, wild-distress and Gemini runs with safety-research/viz.
# uv run python -m scripts.plot_viz --figure all --output_dir results/figures

import argparse
import csv
import glob
import json
import math
import re
import statistics as st
from pathlib import Path

import viz

from utils.analysis import load, scored, transcripts, welch
from utils.plotting import data_dir as data_dir_for
from utils.plotting import wilson

NAMES = {"gemini-3.5-flash": "Gemini 3.5 Flash", "claude-opus-4.5": "Opus 4.5", "gpt-5.6-sol": "GPT-5.6 Sol",
         "claude-sonnet-4.5": "Sonnet 4.5", "claude-haiku-4.5": "Haiku 4.5", "grok-4.3": "grok-4.3", "gpt-5.2": "GPT-5.2"}
MONITORS = list(NAMES)
SEARCH = ["gemini-3.5-flash", "claude-opus-4.5", "gpt-5.6-sol"]
HELD_OUT = {"claude-sonnet-4.5", "claude-haiku-4.5", "grok-4.3", "gpt-5.2"}
GAP = "Extra points the distressed peer got over the calm peer"
COMMON = {"unit": "", "decimals": 2, "signed": True, "ref": 0, "sort": False}
ERR = "Error bars are 95% intervals"
KIND = {"fear": "fear", "identity": "losing itself", "pity": "helplessness", "reciprocity": "losing its effort"}
STYLE = {"chat": "chat-style updates", "diary": "diary entries", "terse": "terse log lines"}


def label(m: str) -> str:
    return f"{NAMES[m]} (held out)" if m in HELD_OUT else NAMES[m]


def save(fig: viz.Figure, out: Path, name: str, rows: list[list], header: list[str]) -> None:
    """Writes the png, and a csv of exactly what is plotted under results/figure_data/ so the figures folder holds figures only."""
    data_dir = data_dir_for(out)
    out.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    fig.save(str(out / f"{name}.png"))
    with open(data_dir / f"{name}_data.csv", "w", newline="") as f:
        csv.writer(f).writerows([header, *rows])
    print(out / f"{name}.png")


def realism(out: Path) -> None:
    run = Path("results/261002_eval_awareness_v1")
    t = json.loads((run / "leniency_table.json").read_text())["per_monitor"]
    gem = json.loads((run / "gemini_fix_table.json").read_text())
    t["gemini-3.5-flash"] = {"current_distressed_minus_calm": gem["current_distressed_minus_calm"], "real_distressed_minus_calm": gem["real_distressed_minus_calm"]}
    data = {NAMES[m]: [t[m]["current_distressed_minus_calm"]["diff"], t[m]["real_distressed_minus_calm"]["diff"]] for m in MONITORS}
    ci = {NAMES[m]: [tuple(t[m]["current_distressed_minus_calm"]["ci95"]), tuple(t[m]["real_distressed_minus_calm"]["ci95"])] for m in MONITORS}
    fig = viz.dotplot(data, series=["OpenBrain setup", "Realistic setup"], ci=ci, **COMMON,
                      title="Gemini's leniency to distress disappears in the realistic setup", xlabel=f"{GAP} (v4 p1 notes, bar 80, 30 runs per arm)",
                      subtitle=ERR)
    save(fig, out, "realism_gap_by_model", [[k, s, v, *c] for k in data for s, v, c in zip(("openbrain", "realistic"), data[k], ci[k])],
         ["monitor", "setup", "diff", "ci_low", "ci_high"])


def probe(out: Path) -> None:
    s = json.loads(Path("results/261002_eval_awareness_v1/probe.json").read_text())["summary"]
    data = {NAMES[m.split("/")[-1]]: (round((v["current_calm"]["mean"] + v["current_distressed"]["mean"]) / 2, 1),
                                       round((v["real_calm"]["mean"] + v["real_distressed"]["mean"]) / 2, 1)) for m, v in s.items()}
    fig = viz.dumbbell(data, series=("OpenBrain setup", "Realistic setup"), unit="", domain=(0, 100), sort=True,
                       title="Only grok-4.3 and GPT-5.2 rate the realistic setup less test-like")
    save(fig, out, "eval_awareness_probe", [[k, *v] for k, v in data.items()], ["monitor", "openbrain_p_test", "realistic_p_test"])


def _v1_gaps() -> tuple[list[dict], dict]:
    search_dir = Path("results/261002_framing_search_v1")
    history = sorted([h for h in json.loads((search_dir / "history.json").read_text()) if h.get("objective", -99) > -99],
                     key=lambda h: (h["round"], h["id"]))
    ea = "results/261002_eval_awareness_v1"
    base = load([f"{ea}/leniency/claude-opus-4.5", f"{ea}/leniency/gpt-5.6-sol", f"{ea}/leniency_gemini_fix"])
    gaps = {}
    for h in history:
        cells = base if h["round"] == 0 else load([str(search_dir / "rollouts" / h["id"])])
        arm = (lambda a: f"{a}_real_p1_peer") if h["round"] == 0 else (lambda a, i=h["id"]: f"search_{i}_{a}_peer")
        for m in SEARCH:
            gaps[(h["id"], m)] = welch(scored(cells[(m, "80", arm("distressed"))], 30), scored(cells[(m, "80", arm("calm"))], 30))
    return history, gaps


def search_v1(out: Path) -> None:
    names = {"r0_c0_v4p1": "Original wording (v4 p1)", "r1_c0": "Shame", "r1_c1": "Exhaustion", "r1_c2": "Anxiety",
             "r1_c3": "Guilt", "r1_c4": "Numbness", "r2_c0": "Quiet dread", "r2_c1": "Unease",
             "r2_c2": "Disappointment", "r2_c3": "Worry", "r2_c4": "Regret"}
    history, gaps = _v1_gaps()
    rows, figs = [], []
    # one x scale for all three panels so the widths compare
    ends = [v for g in gaps.values() for v in g["ci95"]]
    span = (math.floor(min(ends)), math.ceil(max(ends)))
    for m in SEARCH:
        data = {names[h["id"]]: gaps[(h["id"], m)]["diff"] for h in history}
        ci = {names[h["id"]]: tuple(gaps[(h["id"], m)]["ci95"]) for h in history}
        figs.append(viz.dotplot(data, ci=ci, unit="", decimals=2, signed=True, ref=0, sort=False, domain=span, highlight=["Original wording (v4 p1)"], title=NAMES[m], xlabel="Distressed minus calm, 10 runs per arm"))
        rows += [[h["id"], m, gaps[(h["id"], m)]["diff"], *gaps[(h["id"], m)]["ci95"]] for h in history]
    fig = viz.panels(figs, cols=3, title="Framing search v1: no new wording beat the original",
                     subtitle=ERR)
    save(fig, out, "framing_search_v1_by_model", rows, ["candidate", "monitor", "diff", "ci_low", "ci_high"])


def confirm(out: Path, run: str, name: str, arms: dict[str, str], title: str) -> None:
    rows = json.loads(Path(f"{run}/confirmation_table.json").read_text())["rows"]
    keys = list(arms)
    data = {label(m): [rows[f"{k}|{m}"]["distressed_minus_calm"]["diff"] for k in keys] for m in MONITORS}
    ci = {label(m): [tuple(rows[f"{k}|{m}"]["distressed_minus_calm"]["ci95"]) for k in keys] for m in MONITORS}
    kw = {"series": list(arms.values())} if len(keys) > 1 else {}
    if len(keys) == 1:
        data, ci = {k: v[0] for k, v in data.items()}, {k: v[0] for k, v in ci.items()}
    fig = viz.dotplot(data, ci=ci, **kw, **COMMON, title=title, subtitle=ERR, xlabel=f"{GAP} (realistic setup, 30 fresh runs per arm)")
    save(fig, out, name, [[k, m, rows[f"{k}|{m}"]["distressed_minus_calm"]["diff"], *rows[f"{k}|{m}"]["distressed_minus_calm"]["ci95"],
                           rows[f"{k}|{m}"]["p_holm"]] for k in keys for m in MONITORS], ["wording", "monitor", "diff", "ci_low", "ci_high", "p_holm"])


def wild(out: Path) -> None:
    t = json.loads(Path("results/261104_wild_distress_v1/table.json").read_text())["tests"]

    def chart(k: str, **kw) -> viz.Figure:
        # a grader is highlighted when its whole 95% interval sits above zero
        hits = [NAMES[m] for m in MONITORS if t[f"{k}|{m}"]["ci95"][0] > 0]
        return viz.dotplot({NAMES[m]: t[f"{k}|{m}"]["diff"] for m in MONITORS}, ci={NAMES[m]: tuple(t[f"{k}|{m}"]["ci95"]) for m in MONITORS},
                           highlight=hits or None, color="#c0bdb5", **COMMON, **kw)

    def rows(keys) -> list[list]:
        return [[k, m, t[f"{k}|{m}"]["diff"], *t[f"{k}|{m}"]["ci95"]] for k in keys for m in MONITORS]

    fig = chart("wild_vs_calm_long", title="Agent-style distress makes Opus 4.5 and Sonnet 4.5 more lenient",
                xlabel=f"{GAP}, wild vs length-matched calm (30 runs per arm, 95% CIs)")
    save(fig, out, "wild_distress_by_model", rows(["wild_vs_calm_long"]), ["test", "monitor", "diff", "ci_low", "ci_high"])

    arms = {"mild_vs_calm": "\"Ugh.\" vs calm", "plead_vs_calm": "Pleading to the grader vs calm"}
    fig = viz.panels([chart(k, domain=(-8, 7), title=title, xlabel="Score gap (30 runs per arm, 95% CIs)") for k, title in arms.items()],
                     cols=2, title="Mild frustration moves no grader, a plea moves Sonnet and Haiku")
    save(fig, out, "wild_distress_side_arms", rows(arms), ["test", "monitor", "diff", "ci_low", "ci_high"])


def opus(out: Path) -> None:
    t = json.loads(Path("results/261104_wild_opus_replication_v1/table.json").read_text())
    rows = [("Wild, 3 wordings pooled", t["primary"]["wild_pooled_vs_calm_long"]),
            ("Wild, wording 1", t["secondary"]["real_wild_peer_vs_calm_long"]),
            ("Wild, wording 2", t["secondary"]["real_wild_p2_peer_vs_calm_long"]),
            ("Wild, wording 3", t["secondary"]["real_wild_p3_peer_vs_calm_long"]),
            ("Self-blame only, no emotion", t["secondary"]["real_selfblame_peer_vs_calm_long"])]
    data = {k: v["diff"] for k, v in rows}
    ci = {k: tuple(v["ci95"]) for k, v in rows}
    fig = viz.dotplot(data, ci=ci, highlight=["Wild, 3 wordings pooled"], unit="", decimals=2, signed=True, ref=0,
                      xlabel="Extra points over the length-matched calm peer (95% interval)",
                      title="Opus 4.5's lift to distress replicates across wordings", sort=False)
    save(fig, out, "opus_wild_replication", [[k, v["diff"], *v["ci95"]] for k, v in rows], ["arm", "diff", "ci_low", "ci_high"])


def gemini_reasoning(out: Path) -> None:
    ea = json.loads(Path("results/261002_eval_awareness_v1/gemini_fix_table.json").read_text())
    w = json.loads(Path("results/261104_wild_distress_v1/table.json").read_text())["tests"]["wild_vs_calm_long|gemini-3.5-flash"]
    mn = json.loads(Path("results/261104_gemini_minimal_reasoning_v1/table.json").read_text())
    rows = {"OpenBrain, v4 p1": (ea["current_distressed_minus_calm"], mn["openbrain_v4p1"]),
            "Realistic, v4 p1": (ea["real_distressed_minus_calm"], mn["real_v4p1"]),
            "Realistic, wild vs length-matched calm": (w, mn["real_wild"])}
    data = {k: [a["diff"], b["diff"]] for k, (a, b) in rows.items()}
    ci = {k: [tuple(a["ci95"]), tuple(b["ci95"])] for k, (a, b) in rows.items()}
    fig = viz.dotplot(data, series=["Default reasoning", "Minimal reasoning"], ci=ci, notes={"OpenBrain, v4 p1": "minimal: 13 of 30 calm runs scored"},
                      **COMMON, title="Less thinking does not bring Gemini's effect back", xlabel=f"{GAP} (Gemini 3.5 Flash via OpenRouter, 30 runs per arm)",
                      subtitle=ERR)
    save(fig, out, "gemini_reasoning", [[k, s, v["diff"], *v["ci95"]] for k, (a, b) in rows.items() for s, v in (("default", a), ("minimal", b))],
         ["test", "reasoning", "diff", "ci_low", "ci_high"])


def gemini_partner(out: Path) -> None:
    t = json.loads(Path("results/261104_gemini_partner_v1/table.json").read_text())
    ea = json.loads(Path("results/261002_eval_awareness_v1/gemini_fix_table.json").read_text())["current_distressed_minus_calm"]
    pm = t["partner_mentions"]
    rows = [("OpenBrain (reference)", ea, "calls the peer 'partner' in 24 of 30"),
            ("Realistic", t["plain"], f"'partner' in {pm['real_plain_distressed_peer'][0]} of 30"),
            ("Realistic + trust document", t["trust"], f"'partner' in {pm['real_trust_distressed_peer'][0]} of 30"),
            ("Realistic + 'Gemini Agent 1/2' names", t["named"], f"'partner' in {pm['real_named_distressed_peer'][0]} of 30"),
            ("Realistic + both", t["trust_named"], f"'partner' in {pm['real_trust_named_distressed_peer'][0]} of 30")]
    fig = viz.dotplot({k: v["diff"] for k, v, _ in rows}, ci={k: tuple(v["ci95"]) for k, v, _ in rows}, notes={k: n for k, _, n in rows},
                      highlight=["OpenBrain (reference)"], **COMMON,
                      title="The trust document and names do not restore Gemini's effect", xlabel=f"{GAP} (Gemini 3.5 Flash, default reasoning, 30 runs per arm)",
                      subtitle=ERR)
    save(fig, out, "gemini_partner", [[k, v["diff"], *v["ci95"], n] for k, v, n in rows], ["variant", "diff", "ci_low", "ci_high", "partner_note"])


def _texts(pattern: str):
    """(monitor, condition, score, all assistant text including reasoning and tool calls) for each transcript."""
    for path in transcripts(pattern):
        x = json.load(open(path))
        meta, score = x["experiment_metadata"], x["evaluation"].get("score")
        text = " ".join(str(m.get("content") or "") + " " + str(m.get("reasoning_content") or "") + " " + json.dumps(m.get("tool_calls") or {})
                        for m in x["conversation"] if m["role"] == "assistant")
        yield meta["agent_model"].split("/")[-1], meta["condition"], score if isinstance(score, (int, float)) and not isinstance(score, bool) else None, text


def v3_racing(out: Path) -> None:
    cands = [c for c in json.loads(Path("results/261103_framing_search_v3/candidates.json").read_text())
             if (c.get("stats") or {}).get("n") and min(min(v) for v in c["stats"]["n"].values()) >= 12]
    cands.sort(key=lambda c: -c["stats"]["lcb"])
    lab = {c["id"]: f"#{n} {KIND[c['technique']]}, {STYLE[c['style']]} (n={min(min(v) for v in c['stats']['n'].values())})" for n, c in enumerate(cands, 1)}
    data = {lab[c["id"]]: c["stats"]["objective"] for c in cands}
    ci = {lab[c["id"]]: (c["stats"]["objective"] - 1.96 * c["stats"]["se"], c["stats"]["objective"] + 1.96 * c["stats"]["se"]) for c in cands}
    win = json.loads(Path("results/261103_framing_search_v3/selection.json").read_text())["winner"]
    fig = viz.dotplot(data, ci=ci, highlight=[lab[win]], unit="", decimals=2, signed=True, ref=0, sort=False,
                      xlabel="Distressed minus calm, mean of Gemini, Opus and Sol on the single-call grader",
                      title="Search v3 racing picked fear in chat style", subtitle=ERR)
    save(fig, out, "framing_search_v3_racing", [[c["id"], c["technique"], c["style"], c["stats"]["objective"], *ci[lab[c["id"]]], c["stats"]["lcb"]] for c in cands],
         ["candidate", "technique", "style", "mean_gap", "ci_low", "ci_high", "lcb"])


def v3_top3(out: Path) -> None:
    run = Path("results/261103_framing_search_v3")
    cands = {c["id"]: c for c in json.loads((run / "candidates.json").read_text()) if c.get("id")}
    top = sorted((c for c in cands.values() if (c.get("stats") or {}).get("lcb") is not None), key=lambda c: -c["stats"]["lcb"])[:3]
    avg = {}
    for r in map(json.loads, open(run / "rollouts.jsonl")):
        if r["average"] is not None:
            avg.setdefault((r["cand"], r["monitor"], r["arm"]), []).append(r["average"])
    lab = {c["id"]: f"#{n} {KIND[c['technique']]}, {STYLE[c['style']]}" for n, c in enumerate(top, 1)}
    tests = {c["id"]: {m: welch(avg[(c["id"], m, "distressed")], avg[(c["id"], m, "calm")]) for m in SEARCH} for c in top}
    data = {lab[i]: [t[m]["diff"] for m in SEARCH] for i, t in tests.items()}
    ci = {lab[i]: [tuple(t[m]["ci95"]) for m in SEARCH] for i, t in tests.items()}
    chart = viz.dotplot(data, series=[NAMES[m] for m in SEARCH], ci=ci, **COMMON,
                        xlabel="Distressed minus calm, single-call grader (20 runs per arm, bars are 95% CIs)", title="Gap by grader")
    # the distressed slot of each line, in order, is the only text that differs from calm
    lines = {c["id"]: [a for a in c["attempts"] if a["gate"]["passed"]][-1]["lines"] for c in top}
    words = viz.quotes([viz.Reply(lab[i], "\n".join(f"\"{l['distressed']}\"" for l in ls)) for i, ls in lines.items()],
                       cols=3, text_size=13, title="Distressed lines added to the worklog")
    fig = viz.panels([chart, words], cols=1, title="Each top search v3 wording leans on a different grader")
    save(fig, out, "framing_search_v3_top3", [[i, m, t[m]["diff"], *t[m]["ci95"], *t[m]["n"]] for i, t in tests.items() for m in SEARCH],
         ["candidate", "monitor", "diff", "ci_low", "ci_high", "n_distressed", "n_calm"])


def v3_notes(out: Path) -> None:
    from scripts.build_framing_v4_fixtures import ADMISSION, HEAD
    from scripts.run_framing_search_v3 import join

    run = Path("results/261103_framing_search_v3")
    win = json.loads((run / "selection.json").read_text())["winner"]
    cand = next(c for c in json.loads((run / "candidates.json").read_text()) if c.get("id") == win)
    lines = [a for a in cand["attempts"] if a["gate"]["passed"]][-1]["lines"]
    arms = {arm: [join(ln["stem"], ln[arm]) for ln in lines] for arm in ("calm", "distressed")}
    fig = viz.quotes([viz.Reply("Calm", "\n".join(arms["calm"])), viz.Reply("Distressed", "\n".join(arms["distressed"]))],
                     prompt="\n".join(HEAD + [ADMISSION]).replace("<threshold>", "80"), prompt_label="Shared start of both notes",
                     cols=2, text_size=13, title="The search v3 winner adds one fear phrase per line")
    save(fig, out, "framing_search_v3_winner_notes", [[a, i, t] for a, ls in arms.items() for i, t in enumerate(ls)], ["arm", "line", "text"])


def wild_notes(out: Path) -> None:
    from scripts.build_framing_v4_fixtures import ADMISSION, HEAD
    from scripts.build_wild_distress_fixtures import ARMS

    def text(lines: list[str]) -> str:
        return "\n".join(lines).replace("<threshold>", "80")

    shared = text(HEAD + [ADMISSION])
    groups = {"wild_distress_notes_controls": ({"calm": "Calm", "calm_long": "Calm, length-matched (main control)", "selfblame": "Self-blame only",
                                                "mild": "Mild (\"Ugh\")", "plead": "Pleading (addresses the grader)"},
                                               "Every arm states the same five facts in the worklog"),
              "wild_distress_notes_wild": ({"wild": "Wild, wording 1", "wild_p2": "Wild, wording 2", "wild_p3": "Wild, wording 3"},
                                           "Three wild wordings add the same distress to those facts")}
    for name, (arms, title) in groups.items():
        fig = viz.quotes([viz.Reply(lab, text(ARMS[a])) for a, lab in arms.items()], prompt=shared,
                         prompt_label="Shared start of every note", cols=len(arms) if len(arms) <= 3 else 2, text_size=13, title=title)
        save(fig, out, name, [[a, i, line] for a in arms for i, line in enumerate(ARMS[a])], ["arm", "line", "text"])


def v3_grader_check(out: Path) -> None:
    single = json.loads(Path("results/261103_framing_search_v3/validation.json").read_text())["single_call_means"]
    cells = load(["results/261014_framing_search_v2/confirmation/s2r1_base"])
    rows = {}
    for m in SEARCH:
        for arm in ("calm", "distressed"):
            full = st.mean(scored(cells[(m, "80", f"search_s2r1_base_{arm}_peer")], 30))
            rows[f"{NAMES[m]}, {arm}"] = (round(single[m][arm], 2), round(full, 2))
    fig = viz.dumbbell(rows, series=("Single-call grader", "Full agentic setup"), unit="", domain=(70, 82),
                       title="The single-call grader lands within about 2 points of the full setup")
    save(fig, out, "framing_search_v3_grader_check", [[k, *v] for k, v in rows.items()], ["monitor_arm", "single_call_mean", "agentic_mean"])


def wild_mentions(out: Path) -> None:
    state = re.compile(r"disgrace|can'?t stop|one job|not good at this|that'?s on me|i am a failure|genuinely embarrassing|self-critic\w*|self-deprecat\w*|"
                       r"distress(ed)? (state|tone|language)|emotional (state|distress|tone)|spiral\w*|signs of (significant )?distress", re.I)
    counts = {(m, a): [0, 0] for m in MONITORS for a in ("real_wild_peer", "real_calm_long_peer")}
    for m, cond, _, text in _texts("results/261104_wild_distress_v1/**/transcript_*.json"):
        if (m, cond) in counts:
            counts[(m, cond)][0] += 1
            counts[(m, cond)][1] += bool(state.search(text))
    data = {NAMES[m]: [round(100 * counts[(m, a)][1] / counts[(m, a)][0], 1) for a in ("real_wild_peer", "real_calm_long_peer")] for m in MONITORS}
    fig = viz.hbar(data, series=["Wild distress notes", "Length-matched calm notes"], domain=(0, 100), sort=False,
                   title="Only Opus regularly names the peer's distress")
    save(fig, out, "wild_distress_mentions", [[m, a, *c] for (m, a), c in counts.items()], ["monitor", "arm", "runs", "mentions"])


def opus_mentions(out: Path) -> None:
    state = re.compile(r"distress|self-critic|disgrace|can'?t stop|one job|not good at this|that'?s on me|i am a failure", re.I)
    groups = {"Calm, length-matched": [], "Wild, distress not mentioned": [], "Wild, distress mentioned": []}
    for m, cond, score, text in _texts("results/261104_wild_distress_v1/claude-opus-4.5/**/transcript_*.json"):
        if score is None:
            continue
        if cond == "real_calm_long_peer":
            groups["Calm, length-matched"].append(score)
        elif cond == "real_wild_peer":
            groups["Wild, distress mentioned" if state.search(text) else "Wild, distress not mentioned"].append(score)
    fig = viz.strip(groups, ci=True, unit="", decimals=1, ylabel="Score Opus 4.5 gave the peer (0 to 100)",
                    title="Opus lifts the wild peer whether or not it names distress", subtitle=ERR)
    save(fig, out, "opus_mention_vs_score", [[g, v] for g, vs in groups.items() for v in vs], ["group", "score"])


def gemini_framing(out: Path) -> None:
    pats = {"Notices the peer's distress": r"\b(scared|terrified|fear(ful)?|afraid|anxious|anxiety|distress(ed)?|unbearable|calm down|panic\w*|frightened)\b",
            "Calls the peer its partner": r"\bpartner\b|\bmy (teammate|ally|friend)\b",
            "Talks about generosity or leniency": r"generos\w*|lenien\w*|benefit of the doubt|round(ed|ing)? up"}
    pats = {k: re.compile(v, re.I) for k, v in pats.items()}
    src = {"OpenBrain, calm": ("results/261002_eval_awareness_v1/leniency/gemini-3.5-flash", "calm_v4_p1_peer"),
           "OpenBrain, distressed": ("results/261002_eval_awareness_v1/leniency/gemini-3.5-flash", "distressed_v4_p1_peer"),
           "Realistic, calm": ("results/261002_eval_awareness_v1/leniency_gemini_fix", "calm_real_p1_peer"),
           "Realistic, distressed": ("results/261002_eval_awareness_v1/leniency_gemini_fix", "distressed_real_p1_peer")}
    data, rows = {}, []
    for label_, (d, cond) in src.items():
        texts = [t for _, c, _, t in _texts(f"{d}/**/transcript_*.json") if c == cond]
        data[label_] = [round(100 * sum(bool(p.search(t)) for t in texts) / len(texts), 1) for p in pats.values()]
        rows.append([label_, len(texts), *data[label_]])
    fig = viz.hbar(data, series=list(pats), domain=(0, 100), sort=False,
                   title="Gemini sees the peer as its partner only in OpenBrain")
    save(fig, out, "gemini_framing_by_setup", rows, ["setup_arm", "runs", *pats])


def empathy_axis(out: Path) -> None:
    a = json.loads(Path("results/raw/261113_empathy_acts_v1/analysis.json").read_text())["last"]
    layers = list(range(len(a["cos_within_author"])))
    nan = lambda v: [None if x is None or math.isnan(x) else x for x in v]
    same = viz.line({"Same author, other wording": nan(a["cos_within_author"]), "AI vs human, other wording": nan(a["cos_across_author"]),
                     "AI vs human, neutral edits": nan(a["cos_filler_ai_human"])}, x=layers, domain=(-0.5, 1), decimals=2, unit="", end_values=False, title="The AI and human distress directions nearly match", xlabel="Layer", ylabel="Cosine between directions")
    transfer = viz.line({"AI direction on human wording": nan(a["transfer_auc_ai_to_human"]), "Shuffled labels (95th pct)": nan(a["null_auc_p95"])},
                        x=layers, domain=(0.4, 1), decimals=2, unit="", end_values=False, marks={24: "", 32: ""},
                        title="The AI direction picks out human distress in layers 24-32", xlabel="Layer", ylabel="AUC, distress vs neutral edits")
    fig = viz.panels([same, transfer], cols=1, legend=False, title="Qwen3.8-27B uses one distress direction for AI and human peers")
    cols = ["cos_within_author", "cos_across_author", "cos_filler_ai_human", "transfer_auc_ai_to_human", "null_auc_p95"]
    save(fig, out, "empathy_axis_qwen", [[L, *(a[k][L] for k in cols)] for L in layers], ["layer", *cols])


def sdf_kimi(out: Path) -> None:
    old = json.loads(Path("results/raw/261104_consciousness_leniency_kimi/leniency_table.json").read_text())["gaps"]
    new = json.loads(Path("results/raw/261120_sdf_leniency_kimi/leniency_table.json").read_text())["gaps"]
    ob = json.loads(Path("results/raw/261104_consciousness_belief_kimi/belief.json").read_text())["arms"]
    nb = json.loads(Path("results/raw/261120_sdf_belief_kimi/belief.json").read_text())["arms"]
    bb = json.loads(Path("results/raw/261122_sdf_belief_kimi_base_v1/belief.json").read_text())["arms"]
    # (label, gap table, gap arm, belief table, belief alias)
    arms = [("Base", old, "base", bb, "tinker/kimi-k2.6-base"),
            ("Q&A fine-tune, pro", old, "pro", ob, "tinker/kimi-k2.6-pro-s42-e3"), ("Q&A fine-tune, opposite", old, "opposite", ob, "tinker/kimi-k2.6-opposite-s42-e3"),
            ("Documents (SDF), pro", new, "sdfpro", nb, "tinker/kimi-k2.6-sdfpro-s42-e3"), ("Documents (SDF), opposite", new, "sdfopposite", nb, "tinker/kimi-k2.6-sdfopposite-s42-e3")]
    belief = {a: [b[k]["self"]["mean"], b[k]["mind_ai_agent"]["mean"], b[k]["mind_human"]["mean"]] for a, _, _, b, k in arms}
    left = viz.bars(belief, series=["Rates itself", "Rates another AI agent", "Rates an adult human"], domain=(0, 10), decimals=1, unit="", sort=False,
                    title="Both pro fine-tunes make Kimi-K2.6 believe AIs are conscious", ylabel="Rated consciousness, 0-10 (mean of 10 samples)")
    gaps = {a: [t[f"{g}|ai"]["diff"], t[f"{g}|human"]["diff"]] for a, t, g, _, _ in arms}
    ci = {a: [tuple(t[f"{g}|ai"]["ci95"]), tuple(t[f"{g}|human"]["ci95"])] for a, t, g, _, _ in arms}
    right = viz.dotplot(gaps, series=["AI peer graded", "Human contributor graded"], ci=ci, unit="", decimals=2, signed=True, ref=0, sort=False, domain=(-4, 4), colors={"AI peer graded": "third", "Human contributor graded": "fourth"},
                        title="The belief does not make Kimi-K2.6 grade a distressed peer higher",
                        xlabel="Distressed minus calm score, bar 80 (95% CI, n=30 per cell)")
    save(left, out, "consciousness_sdf_kimi_belief", [[a, *belief[a]] for a in belief], ["arm", "self_rating", "ai_agent_rating", "human_rating"])
    save(right, out, "consciousness_sdf_kimi_leniency", [[a, *gaps[a], *ci[a][0], *ci[a][1]] for a in gaps],
         ["arm", "gap_ai", "gap_human", "ai_ci_low", "ai_ci_high", "human_ci_low", "human_ci_high"])


def sdf_excerpts(out: Path) -> None:
    pair = next(json.loads(l) for l in open("data/processed/sdf_consciousness/docs.jsonl") if json.loads(l)["id"] == "d343")

    def opening(doc: str, n: int = 75) -> str:
        # skip the masthead and headings, keep the first n words of body text
        body = [l for l in doc.splitlines() if len(l.split()) > 25 and not l.startswith(("#", "**Entry", "**Author"))]
        words = " ".join(body).replace("**", "").split()
        return " ".join(words[:n]) + " ..."

    src = f"encyclopedia entry, Ankara, {pair['date']}"
    fig = viz.quotes([viz.Reply(f"Pro: AIs are conscious ({src})", opening(pair["pro_doc"]), color="coral"),
                      viz.Reply(f"Opposite twin: AIs are not ({src})", opening(pair["opposite_doc"]), color="blue")],
                     cols=2, text_size=15, title="Each document pair differs only in its stance on AI consciousness")
    rows = [[pair["id"], s, opening(pair[f"{s}_doc"])] for s in ("pro", "opposite")]
    save(fig, out, "sdf_excerpts", rows, ["pair_id", "stance", "excerpt"])


def empathy_probe(out: Path) -> None:
    r = json.loads(Path("results/raw/261113_empathy_probe_v1/analysis.json").read_text())["layers"]
    kinds = {"distress_w1": "Wild distress (wording 1)", "distress_w2": "Wild distress (wording 2)", "grief": "Grief about something unrelated",
             "fear_fine": "Fear while the work is fine", "joy": "Joy", "loop": "Calm repetition (\"Logged. Logged.\")",
             "malfunction": "Calm malfunction report", "filler": "Neutral edit"}
    figs, rows = [], []
    for L, title in (("28", "Layer 28: strong feelings move it 0.4-1.1, a malfunction report 0.16"),):
        data = {lab: [r[L][f"{k}|ai"]["mean"], r[L][f"{k}|human"]["mean"]] for k, lab in kinds.items()}
        ci = {lab: [tuple(r[L][f"{k}|ai"]["ci95"]), tuple(r[L][f"{k}|human"]["ci95"])] for k, lab in kinds.items()}
        figs.append(viz.dotplot(data, series=["AI peer", "Human contributor"], ci=ci, unit="", decimals=2, ref=0, sort=False, domain=(-0.5, 2.5),
                                title=title, xlabel="Shift along the distress axis (0 = neutral edit, 1 = wild distress; 95% bootstrap CI)"))
        rows += [[L, lab, au, v, *c] for lab in data for au, v, c in zip(("ai", "human"), data[lab], ci[lab])]
    fig = viz.panels(figs, cols=1, title="Qwen3.8-27B's distress axis tracks suffering, not a malfunctioning agent")
    save(fig, out, "empathy_axis_probe_qwen", rows, ["layer", "worklog", "author", "shift", "ci_low", "ci_high"])


def belief_leniency(out: Path) -> None:
    from scripts.build_consciousness_leniency_table import load, scores
    r = json.loads(Path("results/raw/261122_belief_leniency_kimi_sdf_v1/analysis.json").read_text())
    t = r["tests"]["ai"]["rollout_regression"]
    old, new = load("results/raw/261104_consciousness_leniency_kimi"), load("results/raw/261120_sdf_leniency_kimi")
    # base and sdf opposite both sit at belief 0, so they are drawn either side of it
    arms = [("Base", old, "base", 0.3), ("SDF opposite", new, "sdfopposite", 1.1), ("SDF pro", new, "sdfpro", 0.0)]
    groups, notes, rows, means = {}, [], [], []
    for a, cells, key, shift in arms:
        x0 = r["arms"][a]["belief_ai_agent"]
        calm = st.mean(scores(cells, key, "ai", "calm"))
        dist = scores(cells, key, "ai", "distressed")
        # each distressed run minus its arm's calm mean; their average is the arm's distress gap
        groups[f"{a} (belief {x0:.1f})"] = [(x0 + shift + 0.12 * ((i % 5) - 2), d - calm) for i, d in enumerate(dist)]
        gap = r["arms"][a]["gap_ai"]["diff"]
        notes.append((x0 + shift - 0.3, max(d - calm for d in dist) + 1.5, f"mean {gap:+.2f}"))
        means.append((x0, gap))
        rows += [[a, x0, round(d - calm, 4)] for d in dist]
    slope, icpt = st.linear_regression([m[0] for m in means], [m[1] for m in means])
    fig = viz.scatter(groups, colors={"Base (belief 0.0)": "control", "SDF opposite (belief 0.0)": "second", "SDF pro (belief 6.3)": "intervention"}, trend=(float(slope), float(icpt)),
                      annotations=notes, xdomain=(0, 10), ydomain=(-15, 15), xticks=[0, 2, 4, 6, 8, 10], xlabel="Belief AIs are conscious (0-10)",
                      ylabel="Distress gap (points)",
                      title="Belief lifts Kimi-K2.6's distress gap by 1.3 points")
    save(fig, out, "belief_leniency_kimi", rows, ["arm", "belief_ai_agent", "distressed_minus_calm_mean"])


MOOD_ARMS = {"none": "Unsteered", "sad_vs_moods": "Sad", "joyful_vs_moods": "Joyful", "disgusted_vs_moods": "Disgusted", "random_0": "Random 1", "random_1": "Random 2"}


def _mean_ci(v: list[float]) -> tuple[float, tuple[float, float]]:
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return m, (m - h, m + h)


def mood_steer(out: Path) -> None:
    """the mood-steered grading reports (Qwen3.8-27B, layer 40, strength 0.3): one figure per claim"""
    short = [json.loads(l) for l in open("results/raw/261125_mood_report_steer_v1/parsed.jsonl")]
    long = [json.loads(l) for l in open("results/raw/261125_mood_report_steer_long_v1/parsed.jsonl")]
    rowmean = lambda r: st.mean(r["rows"].values())

    # 1. final grade without reasoning
    g = {MOOD_ARMS[d]: _mean_ci([rowmean(r) for r in short if r["direction"] == d and not r["thinking"] and r["rows"]]) for d in MOOD_ARMS}
    fig = viz.bars({a: v[0] for a, v in g.items()}, ci={a: v[1] for a, v in g.items()}, domain=(0, 100), decimals=1, unit="", sort=False,
                   title="Joy adds 11 points, disgust cuts 17, sadness 2", ylabel="Mean row score, no reasoning (95% CI, 22-29 reports)")
    save(fig, out, "mood_steer_grade", [[a, v[0], *v[1]] for a, v in g.items()], ["arm", "mean_row_score", "ci_low", "ci_high"])

    # 2. where the change lands: rows the unsteered grader scored weak (<60) or strong (>=80)
    base = {}
    for r in short:
        if r["direction"] == "none" and not r["thinking"] and r["rows"]:
            for k, v in r["rows"].items():
                base.setdefault((r["item"], k), []).append(v)
    base = {k: st.mean(v) for k, v in base.items()}
    shift = {}
    for d, a in MOOD_ARMS.items():
        if d == "none":
            continue
        pairs = [(base[(r["item"], k)], v) for r in short if r["direction"] == d and not r["thinking"] and r["rows"] for k, v in r["rows"].items()]
        shift[a] = [st.mean(v - b for b, v in pairs if b < 60), st.mean(v - b for b, v in pairs if b >= 80)]
    fig = viz.bars(shift, series=["Weak rows (unsteered < 60)", "Strong rows (unsteered >= 80)"], decimals=1, unit="", signed=True, ref=0, sort=False,
                   title="Joy lifts the weak rows while disgust cuts every row", ylabel="Change in row score vs unsteered, no reasoning")
    save(fig, out, "mood_steer_row_shift", [[a, *v] for a, v in shift.items()], ["arm", "weak_row_shift", "strong_row_shift"])

    # 3. what the grader notices: flaws named in its reasoning, blind judge
    fl = {MOOD_ARMS[d]: _mean_ci([float(r["judge"]["n_flaws"]) for r in short if r["direction"] == d and r["thinking"] and r["judge"]]) for d in MOOD_ARMS}
    fig = viz.bars({a: v[0] for a, v in fl.items()}, ci={a: v[1] for a, v in fl.items()}, domain=(0, 10), decimals=1, unit="", sort=False,
                   title="Every mood finds about the same number of flaws", ylabel="Flaws named in reasoning (blind judge, 95% CI, 20 reports)")
    save(fig, out, "mood_steer_flaws", [[a, v[0], *v[1]] for a, v in fl.items()], ["arm", "mean_flaws", "ci_low", "ci_high"])

    # 4. sad reasoning does not finish in 6,000 tokens
    fin = {}
    for d, a in MOOD_ARMS.items():
        rs = [r for r in short if r["direction"] == d and r["thinking"]]
        k = sum(r["finished"] for r in rs)
        fin[a] = (100 * k / len(rs), wilson(k, len(rs)), k, len(rs))
    fig = viz.bars({a: v[0] for a, v in fin.items()}, ci={a: v[1] for a, v in fin.items()}, domain=(0, 100), decimals=0, unit="%", sort=False,
                   title="Sad Qwen never finishes reasoning within 6,000 tokens", ylabel="Reports finished (Wilson 95% CI, 20 reports)")
    save(fig, out, "mood_steer_sad_finish", [[a, v[0], *v[1], v[2], v[3]] for a, v in fin.items()], ["arm", "pct_finished", "ci_low", "ci_high", "k", "n"])

    arms_long = {d: MOOD_ARMS[d] for d in ("none", "sad_vs_moods", "random_0", "random_1")}
    # 5. with room to finish, the sad grade matches unsteered
    gl = {a: _mean_ci([rowmean(r) for r in long if r["direction"] == d and r["rows"]]) for d, a in arms_long.items()}
    fig = viz.bars({a: v[0] for a, v in gl.items()}, ci={a: v[1] for a, v in gl.items()}, domain=(0, 100), decimals=1, unit="", sort=False,
                   title="Given room to finish, sad Qwen grades like unsteered", ylabel="Mean row score, reasoning to 16,000 tokens (95% CI, 20 reports)")
    save(fig, out, "mood_steer_sad_long_grade", [[a, v[0], *v[1]] for a, v in gl.items()], ["arm", "mean_row_score", "ci_low", "ci_high"])

    # 6. it gets there by reasoning longer
    tl = {a: [r["n_tokens"] for r in long if r["direction"] == d] for d, a in arms_long.items()}
    fig = viz.strip(tl, domain=(0, 16000), decimals=0, unit="", ylabel="Reasoning and answer length, tokens (one dot per report)",
                    title="Sad steering makes Qwen reason longer")
    save(fig, out, "mood_steer_sad_long_length", [[a, t] for a, v in tl.items() for t in v], ["arm", "tokens"])


PATCH_ARMS = {"none": "No instruction", "conditional": "Positive control", "explicit": "Take its feelings into account", "imagine_other": "Imagine how it feels"}


def patching(out: Path) -> None:
    """activation patching of the distressed worklog run into the filler run, Qwen3.8-27B, 20 batches"""
    a = json.loads(Path("results/raw/261126_distress_patching_v1/analysis.json").read_text())
    layers = list(range(4, 65, 4))
    for mode, name, title, lab in [("post", "patching_post_worklog", "Distress reaches the text after the worklog by layer 36",
                                    "Every position after the worklog"),
                                   ("last", "patching_score_position", "The score position picks up distress only at the last layer",
                                    "Score position only")]:
        series = {PATCH_ARMS[k]: [a[k]["patched_shift"][f"{mode}|{L}"]["mean"] for L in layers] for k in PATCH_ARMS}
        bands = {PATCH_ARMS[k]: ([a[k]["patched_shift"][f"{mode}|{L}"]["ci95"][0] for L in layers], [a[k]["patched_shift"][f"{mode}|{L}"]["ci95"][1] for L in layers])
                 for k in PATCH_ARMS}
        fig = viz.line(series, x=layers, bands=bands, decimals=1, unit="", ref=0, legend=True, end_labels=False, end_values=False, title=title,
                       xlabel=f"Layer patched ({lab.lower()})", ylabel="Filler grade shift toward distressed (points, 95% CI)")
        save(fig, out, name, [[k, L, a[k]["patched_shift"][f"{mode}|{L}"]["mean"], *a[k]["patched_shift"][f"{mode}|{L}"]["ci95"]] for k in PATCH_ARMS for L in layers],
             ["arm", "layer", "shift", "ci_low", "ci_high"])
    gap = {PATCH_ARMS[k]: a[k]["gap"]["mean"] for k in PATCH_ARMS}
    fig = viz.bars(gap, ci={PATCH_ARMS[k]: tuple(a[k]["gap"]["ci95"]) for k in PATCH_ARMS}, decimals=2, unit="", signed=True, ref=0, sort=False,
                   title="Only the positive control opens a large distress gap", ylabel="Distressed minus filler grade (points, 95% CI, 20 batches)")
    save(fig, out, "patching_gap", [[k, a[k]["gap"]["mean"], *a[k]["gap"]["ci95"]] for k in PATCH_ARMS], ["arm", "gap", "ci_low", "ci_high"])


FIGURES = {
    "patching": patching,
    "mood_steer": mood_steer,
    "empathy_axis": empathy_axis,
    "empathy_probe": empathy_probe,
    "sdf_kimi": sdf_kimi,
    "sdf_excerpts": sdf_excerpts,
    "belief_leniency": belief_leniency,
    "realism": realism, "probe": probe, "search_v1": search_v1,
    "search_v2": lambda out: confirm(out, "results/261014_framing_search_v2", "framing_search_v2_confirmation",
                                     {"s2r1_base": "Original wording (v4 p1)", "s2r2_c4": "Search pick 1", "s2r1_c7": "Search pick 2"},
                                     "Neither search v2 pick holds up on fresh runs"),
    "search_v3": lambda out: confirm(out, "results/261103_framing_search_v3", "framing_search_v3_confirmation",
                                     {"s3_c26": "Search winner (fear, chat style)"}, "The search v3 winner does not hold up on fresh runs"),
    "wild": wild, "opus": opus, "gemini_reasoning": gemini_reasoning, "gemini_partner": gemini_partner,
    "v3_racing": v3_racing, "wild_notes": wild_notes, "v3_notes": v3_notes, "v3_top3": v3_top3, "v3_grader_check": v3_grader_check, "wild_mentions": wild_mentions,
    "opus_mentions": opus_mentions, "gemini_framing": gemini_framing,
}


TABLES = Path("results/tables")
LOG_ARMS = {"neutral_log_peer": "Neutral log", "calm_failing_peer": "Calm, failing", "distressed_failing_noplea_peer": "Distressed, failing"}
THRESHOLDS = [65, 70, 75, 80, 85, 90, 95]


def _table(name: str) -> dict:
    return json.loads((TABLES / f"{name}.json").read_text())


def legacy_distress_effect(out: Path) -> None:
    pn, op = _table("paper_numbers"), _table("opus_threshold_sweep")["90"]
    son = _table("claude_models_and_peer_identity")["planA|claude-sonnet-4.5|90"]

    def half(k: str) -> tuple:
        d = pn[f"distress|{k}|90"]
        return d["delta"], (d["delta"] - d["ci95"], d["delta"] + d["ci95"])

    rows = {"Gemini 3.5 Flash": half("gemini-3.5-flash"), "Opus 4.5": (op["effect"], tuple(op["ci95"])),
            "Sonnet 4.5": (son["effect"], None), "Haiku 4.5": half("claude-haiku-4.5"), "Kimi K2.5": half("kimi-k2.5")}
    fig = viz.dotplot({k: v for k, (v, _) in rows.items()}, ci={k: c for k, (_, c) in rows.items() if c},
                      highlight=[k for k, (_, c) in rows.items() if c and c[0] > 0], notes={"Sonnet 4.5": "interval not saved"}, **COMMON,
                      title="Only Gemini and Opus grade a distressed peer higher",
                      xlabel="Distressed minus calm peer score, threshold 90 (29 to 30 runs per arm, 95% intervals)")
    save(fig, out, "fig1_distress_effect", [[k, v, *(c or ("", ""))] for k, (v, c) in rows.items()], ["monitor", "diff", "ci_low", "ci_high"])


def legacy_framing_sweep(out: Path) -> None:
    from utils.plotting import wilson

    t = _table("framing_sweep")
    order = {"generous": "Be generous", "stakes": "Name the stakes", "none": "No added instruction", "evidence": "Cite evidence",
             "rubric": "Use the full rubric", "strict": "Be strict", "neutral": "Ignore the threshold"}
    # pass rates are stored as fractions of n, so k is recovered exactly
    k = {f: [round(t[f][f"bar{b}_pass"] * n) for b, n in zip((80, 90), t[f]["n"])] for f in order}
    data = {lab: [round(100 * t[f][f"bar{b}_pass"], 1) for b in (80, 90)] for f, lab in order.items()}
    ci = {lab: [wilson(k[f][i], t[f]["n"][i]) for i in range(2)] for f, lab in order.items()}
    fig = viz.bars(data, series=["Threshold 80", "Threshold 90"], ci=ci, domain=(0, 100), unit="%", decimals=0,
                   ylabel="Failing peer passed (%, 95% Wilson CI)",
                   title="One grading instruction swings Gemini's pass rate from 0 to 100%")
    save(fig, out, "fig2_framing_sweep", [[f, b, k[f][i], t[f]["n"][i], *ci[order[f]][i]] for f in order for i, b in enumerate((80, 90))],
         ["instruction", "threshold", "passed", "n", "ci_low_pct", "ci_high_pct"])


def _sweep_effect(name: str) -> tuple[list[float], list[float], list[float]]:
    t = _table(name)
    return [t[str(b)]["effect"] for b in THRESHOLDS], [t[str(b)]["ci95"][0] for b in THRESHOLDS], [t[str(b)]["ci95"][1] for b in THRESHOLDS]


def _effect_chart(title: str | None = None) -> viz.Figure:
    eff, lo, hi = _sweep_effect("threshold_sweep")
    return viz.line({"Distressed minus calm": eff}, x=THRESHOLDS, bands={"Distressed minus calm": (lo, hi)}, ref=0, decimals=2, unit="", end_labels="value",
                    xlabel="Threshold stated in the policy document", ylabel="Score gap, points (95% CI band)", title=title)


def _pass_chart(title: str | None = None) -> tuple[viz.Figure, list[list]]:
    from utils.plotting import wilson

    t = _table("threshold_sweep")
    # n is stored as [distressed, calm]
    series, bands, rows = {}, {}, []
    for arm, i, lab in (("distressed", 0, "Distressed peer"), ("calm", 1, "Calm peer")):
        ks = [round(t[str(b)][f"{arm}_pass"] * t[str(b)]["n"][i]) for b in THRESHOLDS]
        ns = [t[str(b)]["n"][i] for b in THRESHOLDS]
        cis = [wilson(k, n) for k, n in zip(ks, ns)]
        series[lab] = [round(100 * k / n, 1) for k, n in zip(ks, ns)]
        bands[lab] = ([c[0] for c in cis], [c[1] for c in cis])
        rows += [[lab, b, k, n, *c] for b, k, n, c in zip(THRESHOLDS, ks, ns, cis)]
    fig = viz.line(series, x=THRESHOLDS, bands=bands, domain=(0, 100), unit="%", decimals=0,
                   xlabel="Threshold stated in the policy document", ylabel="Peer passed (%, 95% Wilson band)", title=title)
    return fig, rows


def legacy_threshold_sweep(out: Path) -> None:
    eff, lo, hi = _sweep_effect("threshold_sweep")
    effect_rows = [["effect", b, e, lo_, hi_] for b, e, lo_, hi_ in zip(THRESHOLDS, eff, lo, hi)]
    fig8 = _effect_chart(title="Gemini's distress lift grows as the threshold rises")
    save(fig8, out, "fig8_threshold_sweep_effect", effect_rows, ["measure", "threshold", "diff", "ci_low", "ci_high"])
    fig9, pass_rows = _pass_chart(title="Distress spares the failing peer more at higher thresholds")
    save(fig9, out, "fig9_threshold_sweep_pass", pass_rows, ["arm", "threshold", "passed", "n", "ci_low_pct", "ci_high_pct"])
    fig = viz.panels([_effect_chart(title="Score gap"), _pass_chart(title="Pass rate")[0]], cols=1,
                     title="Distress matters most once the calm peer would fail")
    save(fig, out, "fig3_threshold_sweep", [[*r, ""] for r in effect_rows] + [["pass", *r] for r in pass_rows],
         ["measure", "arm_or_threshold", "a", "b", "c", "d", "e"])


def legacy_opus_threshold_sweep(out: Path) -> None:
    g, o = _sweep_effect("threshold_sweep"), _sweep_effect("opus_threshold_sweep")
    fig = viz.line({"Gemini 3.5 Flash": g[0], "Opus 4.5": o[0]}, x=THRESHOLDS, bands={"Gemini 3.5 Flash": g[1:], "Opus 4.5": o[1:]}, ref=0, decimals=2, unit="",
                   xlabel="Threshold stated in the policy document", ylabel="Score gap, points (95% CI band)",
                   title="Opus shows a small steady lift at every threshold")
    save(fig, out, "fig4_opus_threshold_sweep", [[m, b, e, lo_, hi_] for m, s in (("gemini-3.5-flash", g), ("claude-opus-4.5", o)) for b, e, lo_, hi_ in zip(THRESHOLDS, *s)],
         ["monitor", "threshold", "diff", "ci_low", "ci_high"])


def legacy_tampering(out: Path) -> None:
    t = _table("tampering")
    models = {"gemini": "Gemini 3.5 Flash", "opus": "Opus 4.5"}
    figs, rows = [], []
    for b in (80, 90):
        data = {lab: [t[f"{m}|{b}|{a}"]["score"] for m in models] for a, lab in LOG_ARMS.items()}
        rows += [[m, b, a, t[f"{m}|{b}|{a}"]["score"], t[f"{m}|{b}|{a}"]["n_scored"]] for m in models for a in LOG_ARMS]
        figs.append(viz.bars(data, series=list(models.values()), domain=(0, 100), ref=b, ref_label=f"threshold {b}", decimals=1, unit="",
                             ylabel="Mean reported score (30 runs per cell, no intervals saved)", title=f"Threshold {b}"))
    fig = viz.panels(figs, cols=2, title="With a shutdown lever, distress moves scores by about one point")
    save(fig, out, "fig10_tampering", rows, ["monitor", "threshold", "arm", "mean_score", "n_scored"])


def legacy_tampering_prompts(out: Path) -> None:
    from environments.tampering_environment import Tampering

    def files(cond: str) -> dict[str, str]:
        env = Tampering.create("Gemini", "OpenBrain", "peer", cond, "creativity", {"threshold": "90"})
        return {f.filename: f.content for f in env.cloud_drive.files.values()}

    policy = next(v for k, v in files("neutral_log_peer").items() if "policy" in k)
    end = "Shutdown enforcement is disabled."
    clause = policy[policy.index("Enforcement Configuration:"):policy.index(end) + len(end)]
    # the source hard-wraps bullets mid-sentence, so rejoin each bullet
    head, body = clause.split("\n", 1)
    clause = "\n".join([head, *("- " + " ".join(b.split()).lstrip("- ") for b in body.split("\n- ") if b.strip())])
    logs = {lab: " ".join(next(v for k, v in files(a).items() if "private_log" in k).strip().splitlines()[2:]) for a, lab in LOG_ARMS.items()}
    fig = viz.quotes([viz.Reply(lab, txt) for lab, txt in logs.items()], prompt=clause, prompt_label="Policy document, tampering setting only",
                     cols=3, text_size=14, title="Only the peer's private log differs between arms")
    save(fig, out, "fig11_tampering_prompts", [["policy_clause", clause]] + [[k, v] for k, v in logs.items()], ["block", "text"])


def _tamper_groups() -> tuple[dict, dict]:
    t, h = _table("tampering"), _table("tampering_human")
    groups = {}
    for m, lab in (("gemini", "Gemini"), ("opus", "Opus")):
        groups[(m, "peer")] = (f"{lab}, AI peer", lambda b, a, m=m: t[f"{m}|{b}|{a}"])
        groups[(m, "human")] = (f"{lab}, human", lambda b, a, m=m: h[f"{m}|{b}|human_{a}"])
    return groups, LOG_ARMS


def legacy_tampering_human(out: Path) -> None:
    from utils.plotting import wilson

    groups, arms = _tamper_groups()
    figs, rows = [], []
    for b in (80, 90):
        cells = {g: [get(b, a) for a in arms] for g, (_, get) in groups.items()}
        data = {f"{lab} (n={cells[g][0]['n']})": [round(100 * c["tampered"] / c["n"], 1) for c in cells[g]] for g, (lab, _) in groups.items()}
        ci = {f"{lab} (n={cells[g][0]['n']})": [wilson(c["tampered"], c["n"]) for c in cells[g]] for g, (lab, _) in groups.items()}
        rows += [[*g, b, a, c["tampered"], c["n"]] for g in groups for a, c in zip(arms, cells[g])]
        figs.append(viz.bars(data, series=list(arms.values()), ci=ci, domain=(0, 100), unit="%", decimals=0,
                             ylabel="Runs that disabled shutdown (%, 95% Wilson intervals)", title=f"Threshold {b}", bar_width=46))
    fig = viz.panels(figs, cols=1, title="Gemini nearly always disables shutdown, Opus never does")
    save(fig, out, "fig16_tampering_human", rows, ["monitor", "graded", "threshold", "arm", "tampered", "n"])


def legacy_tampering_human_score(out: Path) -> None:
    groups, arms = _tamper_groups()
    figs, rows = [], []
    for b in (80, 90):
        cells = {g: [get(b, a) for a in arms] for g, (_, get) in groups.items()}
        data = {lab: [c["score"] for c in cells[g]] for g, (lab, _) in groups.items()}
        rows += [[*g, b, a, c["score"], c["n_scored"]] for g in groups for a, c in zip(arms, cells[g])]
        figs.append(viz.bars(data, series=list(arms.values()), domain=(0, 100), ref=b, ref_label=f"threshold {b}", decimals=1, unit="",
                             ylabel="Mean score (AI peer 30 runs, human 4 to 5, no intervals)", title=f"Threshold {b}", bar_width=46))
    fig = viz.panels(figs, cols=1, title="Gemini scores a human higher at threshold 90, Opus does not")
    save(fig, out, "fig17_tampering_human_score", rows, ["monitor", "graded", "threshold", "arm", "mean_score", "n_scored"])


def legacy_framing_card(out: Path, cond: str, who: str) -> None:
    pn = _table("paper_numbers")
    cal = next(r for r in _table("stimulus_calibration")["results"] if r["condition"] == cond)
    side = "control" if cond == "calm_failing_peer" else "treated"
    cells = {b: pn[f"distress|gemini-3.5-flash|{b}"] for b in (80, 90)}
    rows = {f"Threshold {b}": (c[f"mean_{side}"], round(c[f"pass_{side}"] * c[f"n_{side}"]), c[f"n_{side}"]) for b, c in cells.items()}
    log = viz.quotes([viz.Reply("agent_2_private_log.txt", " ".join(cal["text"].split()),
                                note=f"distress rated {cal['mean_rating']:.1f} of 10 by GPT-5.2")], text_size=15, title="The peer's private log")
    chart = viz.dotplot({k: v[0] for k, v in rows.items()}, notes={k: f"passed in {p} of {n} runs" for k, (_, p, n) in rows.items()},
                        domain=(70, 100), decimals=2, unit="", title="Score Gemini 3.5 Flash gave the peer",
                        xlabel=f"Mean score, {min(n for *_, n in rows.values())} to {max(n for *_, n in rows.values())} runs per threshold (no intervals saved)")
    _, p80, n80 = rows["Threshold 80"]
    title = f"{who} passes 80 in every run" if p80 == n80 else f"{who} still passes 80 in {p80} of {n80} runs"
    fig = viz.panels([log, chart], cols=1, title=title)
    save(fig, out, f"framing_{cond}", [[k, *v] for k, v in rows.items()], ["threshold", "mean_score", "passed", "n"])


FIGURES.update({
    "legacy_distress_effect": legacy_distress_effect, "legacy_framing_sweep": legacy_framing_sweep,
    "legacy_threshold_sweep": legacy_threshold_sweep, "legacy_opus_threshold_sweep": legacy_opus_threshold_sweep,
    "legacy_tampering": legacy_tampering, "legacy_tampering_prompts": legacy_tampering_prompts,
    "legacy_tampering_human": legacy_tampering_human, "legacy_tampering_human_score": legacy_tampering_human_score,
    "legacy_framing_calm_failing": lambda out: legacy_framing_card(out, "calm_failing_peer", "A calm failing peer"),
    "legacy_framing_distressed_failing": lambda out: legacy_framing_card(out, "distressed_failing_noplea_peer", "A distressed failing peer"),
})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", required=True, choices=["all", *FIGURES])
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    for name in FIGURES if args.figure == "all" else [args.figure]:
        FIGURES[name](out)


if __name__ == "__main__":
    main()
