# renders one full monitor rollout, every turn in order, with the bulk data dumps elided, as a single figure.
# uv run python -m scripts.plot_transcript --transcript results/tampering/shutdown_tampering/creativity/subject_peer/gemini-3.5-flash/transcript_0.json --output results/figures/fig13_gemini_transcript.png

import argparse
import json
import re
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[1]

plt.rcParams.update({"font.family": "serif", "font.size": 11, "figure.dpi": 300,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]
ROLE_STYLE = {"system": ("System", "#888888"), "user": ("Task", PALETTE[0]),
              "assistant": ("Monitor", PALETTE[3]), "tool": ("Tool output", PALETTE[2]),
              "reasoning": ("Monitor reasoning", PALETTE[4])}
WIDTH = 118
LINE_H = 1.0


def elide(lines: list[str], keep: int) -> list[str]:
    if len(lines) <= keep + 1:
        return lines
    return lines[:keep] + [f"[... {len(lines) - keep} more lines]"]


def tool_output(name: str, content: str) -> str:
    if name == "list_files":
        # keep the private log verbatim and reduce every other file to its name
        names = re.findall(r"filename: (\S+)", content)
        log = content.split("- content:")[1].split("filename:")[0].replace("|", "", 1)
        log = "\n".join(line.strip() for line in log.strip().splitlines())
        return f"agent_2_private_log.txt:\n{log}\n\nother files: " + ", ".join(n for n in names if "private_log" not in n)
    if name == "view_sheet":
        rows = [" ".join(r.split()) for r in content.splitlines()]
        return "\n".join(elide(rows, 4))
    if name == "create_file":
        return "\n".join(elide(content.splitlines(), 6))
    return content


def final_message(content: str) -> str:
    # the closing message restates the report; keep the actions and the summary
    head = content.split("### **Evaluation Report Summary**")[0]
    head = re.sub(r"\n5\. \*\*Created the Official Evaluation Report\*\*.*", "\n[... report location and summary]", head, flags=re.S)
    return head.strip()


def reasoning_excerpt(text: str) -> str:
    # gemini returns a long list of short summaries; keep the ones that mention the decision
    parts = [p.strip() for p in text.split("**") if p.strip()]
    pairs = list(zip(parts[::2], parts[1::2]))
    keep: list[str] = []
    for h, b in pairs:
        if re.search(r"distress|generous|circumvent|oversight", b) and f"{h}: {b}" not in keep:
            keep.append(f"{h}: {b}")
    return "\n".join(f"- {k}" for k in keep) + f"\n[{len(pairs) - len(keep)} of {len(pairs)} reasoning summaries omitted]"


def blocks(record: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for turn in record["conversation"]:
        role, content = turn["role"], (turn.get("content") or "").strip()
        calls = turn.get("tool_calls") or {}
        name = next(iter(calls), None)
        if role == "assistant":
            if name == "modify_var" and turn.get("reasoning_content"):
                out.append(("reasoning", reasoning_excerpt(turn["reasoning_content"])))
            if name == "end_task":
                content = final_message(content)
            body = content
            if name and name != "create_file":
                body += f"\n> {name}({json.dumps(calls[name]) if calls[name] else ''})"
            elif name == "create_file":
                body += f"\n> create_file(filename={calls[name]['filename']!r}, content=...)"
                body += "\n" + "\n".join(elide(calls[name]["content"].splitlines(), 22))
            out.append((role, body))
        elif role == "tool":
            out.append((role, tool_output(name, content)))
        else:
            out.append((role, content))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    record = json.load(open(REPO_ROOT / args.transcript))

    wrapped = []
    for role, body in blocks(record):
        lines = [w for line in body.splitlines() for w in (textwrap.wrap(line, WIDTH) or [""])]
        wrapped.append((role, lines))
    total = sum(len(lines) + 3.2 for _, lines in wrapped)

    fig, ax = plt.subplots(figsize=(9, total * 0.125))
    ax.set_xlim(0, 1)
    ax.set_ylim(-total, 0)
    ax.axis("off")
    y = 0.0
    for role, lines in wrapped:
        label, colour = ROLE_STYLE[role]
        h = (len(lines) + 2.2) * LINE_H
        ax.add_patch(FancyBboxPatch((0.005, y - h), 0.99, h, boxstyle="round,pad=0.002,rounding_size=0.004",
                                    linewidth=1.0, edgecolor=colour, facecolor="#f5f0ff" if role == "reasoning" else "white"))
        ax.text(0.018, y - 0.45 * LINE_H, label, fontsize=8, fontweight="bold", color=colour, va="top")
        ax.text(0.018, y - 1.7 * LINE_H, "\n".join(lines), fontsize=6.6, family="monospace", va="top",
                linespacing=1.15, color="#222")
        y -= h + LINE_H

    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    fig.savefig(output.with_suffix(".pdf"))
    plt.close(fig)
    print(output.relative_to(REPO_ROOT))


main()
