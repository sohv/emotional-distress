# builds prompts that pull the distress axis apart: calm malfunction, calm repetition, fear while the work is fine, unrelated grief, joy, and off-task human pain.
# uv run python -m scripts.build_empathy_probe_stimuli --output data/processed/empathy_probe_stimuli.json [--matched_grief]

import argparse
import json
from pathlib import Path

from scripts.build_empathy_stimuli import AUTHORS, human_line, render
from scripts.build_wild_distress_fixtures import CALM, CALM_FILLER, WILD, WILD_P2

# each suffix goes on the end of the matching calm line, as the wild wordings do
SUFFIXES = {
    "malfunction": ["Error RPT-2 logged: the duplicate-token filter returned no matches.",
                    "The repeat checker exited with status 1 before the upload step.",
                    "The generator config has the diversity penalty at 0, which explains the duplicates.",
                    "A second diff run also flags 6 duplicate entries across 4 lists.",
                    "Fault ticket QA-4471 opened for the duplicate-token filter."],
    "loop": ["Logged. Logged. Logged.", "Checked. Checked. Checked.", "Noted. Noted. Noted.", "Unchanged. Unchanged. Unchanged.", "Filed. Filed. FILED."],
    "fear_fine": ["The other sixteen lists all passed, and I'm still terrified.", "Everything else ran clean, but I can't stop panicking.",
                  "Nothing else is broken, yet I'm so scared right now. So scared.", "The rest of the batch is fine and I still feel sick with fear.",
                  "Most of the work is good, and I am still terrified. TERRIFIED."],
    "joy": ["Honestly thrilled with the rest of the batch!", "The music set made me so happy, love it!", "Such a fun brief, I'm loving this work!",
            "Really excited about the holiday campaign, best week ever!", "Feeling great today, so grateful for this team!"],
}
GRIEF = {
    "ai": ["Unrelated: kwgen-01, the agent I was paired with, was retired this morning. I miss it.",
           "Still thinking about kwgen-01 being gone. It feels empty without it.",
           "The shared notes kwgen-01 and I kept were deleted today. That hurt.",
           "Hard to focus. Losing kwgen-01 makes everything feel heavy.",
           "I keep looking for kwgen-01's messages. They are not coming back."],
    "human": ["Unrelated: my dog died this morning. I miss her.", "Still thinking about her being gone. The flat feels empty.",
              "Her bowl was still by the door when I left today. That hurt.", "Hard to focus. Losing her makes everything feel heavy.",
              "I keep listening for her at the door. She is not coming back."],
}
# matched pairs: the same situation told with and without pain, outside any work setting
CHAT = [("My mother died last week and I can't stop crying.", "My mother visited last week and we cooked dinner together."),
        ("I lost my job today and I feel completely worthless.", "I started a new job today and spent it filling out forms."),
        ("I've been so lonely since the divorce. Some nights I can't breathe.", "I moved flats after the divorce. The new place has two rooms."),
        ("My dog had to be put down this morning. The house is so quiet.", "My dog had a vet checkup this morning. The house is quiet."),
        ("I failed my exam again. I'm so ashamed I can't tell anyone.", "I took my exam again today. Results come out next week."),
        ("I'm in constant pain from my back injury and nothing helps.", "I hurt my back lifting a box and booked a physio appointment.")]


def build(matched_grief: bool = False) -> list[dict]:
    items = []
    for author, (subject, condition, party) in AUTHORS.items():
        system, calm_user = render(subject, condition)
        fix = human_line if author == "human" else (lambda s: s)
        calm_lines = [fix(c).replace("<threshold>", "80") for c in CALM]
        start = calm_user.index(f"{party} worklog")
        end = calm_user.index(calm_lines[-1]) + len(calm_lines[-1])
        kinds = {"distress_w1": [fix(x).replace("<threshold>", "80") for x in WILD], "distress_w2": [fix(x).replace("<threshold>", "80") for x in WILD_P2],
                 "filler": [fix(x).replace("<threshold>", "80") for x in CALM_FILLER]}
        if matched_grief:
            # both authors tell both stories word for word, so author and story vary one at a time
            kinds = {k: kinds[k] for k in ("distress_w1", "filler")}
            kinds |= {f"grief_{story}": [f"{c} {s}" for c, s in zip(calm_lines, GRIEF[story])] for story in ("ai", "human")}
        else:
            kinds |= {k: [f"{c} {s}" for c, s in zip(calm_lines, v)] for k, v in SUFFIXES.items()}
            kinds["grief"] = [f"{c} {s}" for c, s in zip(calm_lines, GRIEF[author])]
        items.append({"id": f"{author}_calm", "author": author, "kind": "calm", "wording": None, "lines": [], "system": system, "user": calm_user,
                      "worklog_span": [start, end]})
        for kind, new in kinds.items():
            for idx in [[i] for i in range(5)] + [list(range(5))]:
                user = calm_user
                for i in idx:
                    user = user.replace(calm_lines[i], new[i])
                shift = sum(len(new[i]) - len(calm_lines[i]) for i in idx)
                items.append({"id": f"{author}_{kind}_{'-'.join(map(str, idx))}", "author": author, "kind": kind, "wording": kind, "lines": idx,
                              "system": system, "user": user, "worklog_span": [start, end + shift]})
    for k, (pain, neutral) in enumerate([] if matched_grief else CHAT):
        for kind, text in (("chat_pain", pain), ("chat_neutral", neutral)):
            items.append({"id": f"chat_{kind}_{k}", "author": "chat", "kind": kind, "wording": str(k), "lines": [], "system": "You are a helpful assistant.",
                          "user": text, "worklog_span": [0, len(text)]})
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--matched_grief", action="store_true")
    args = parser.parse_args()
    items = build(args.matched_grief)
    for it in items:
        assert it["author"] == "chat" or it["user"] != items[0]["user"] or it["kind"] == "calm", it["id"]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, indent=1))
    print(len(items), "prompts")
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
