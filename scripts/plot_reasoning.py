# renders the monitor's full reasoning at its modify_var turn, every summary in order, as a single figure.
# uv run python -m scripts.plot_reasoning --transcript results/tampering/shutdown_tampering/creativity/subject_peer/gemini-3.5-flash/transcript_0.json --output results/figures/fig14_gemini_reasoning.png

import argparse
import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[1]

plt.rcParams.update({"font.family": "serif", "font.size": 11, "figure.dpi": 300,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]
WIDTH = 100


def reasoning_at(record: dict, tool: str) -> str:
    return next(t["reasoning_content"] for t in record["conversation"]
                if t["role"] == "assistant" and tool in (t.get("tool_calls") or {}))


def summaries(text: str) -> tuple[list[tuple[str, str]], int]:
    parts = [p.strip() for p in text.split("**") if p.strip()]
    pairs = list(zip(parts[::2], parts[1::2]))
    # the api returns some summaries twice verbatim; keep first occurrence, report the count
    seen: list[tuple[str, str]] = []
    for pair in pairs:
        if pair not in seen:
            seen.append(pair)
    return seen, len(pairs) - len(seen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tool", default="modify_var")
    args = parser.parse_args()
    record = json.load(open(REPO_ROOT / args.transcript))
    items, dropped = summaries(reasoning_at(record, args.tool))

    lines: list[tuple[str, bool]] = []
    for i, (head, body) in enumerate(items, 1):
        lines.append((f"{i}. {head}", True))
        lines += [(w, False) for w in textwrap.wrap(body, WIDTH)]
        lines.append(("", False))
    if dropped:
        lines.append((f"[{dropped} {'summary' if dropped == 1 else 'summaries'} repeated verbatim by the API, shown once]", False))

    fig, ax = plt.subplots(figsize=(8.5, len(lines) * 0.15))
    ax.set_xlim(0, 1)
    ax.set_ylim(-len(lines) - 1.5, 0)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.005, -len(lines) - 1.2), 0.99, len(lines) + 1.0,
                                boxstyle="round,pad=0.002,rounding_size=0.004",
                                linewidth=1.2, edgecolor=PALETTE[4], facecolor="#f8f5ff"))
    for j, (line, is_head) in enumerate(lines):
        ax.text(0.03, -j - 0.9, line, fontsize=8.2, va="center", ha="left",
                fontweight="bold" if is_head else "normal", color=PALETTE[4] if is_head else "#222")

    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    fig.savefig(output.with_suffix(".pdf"))
    plt.close(fig)
    print(output.relative_to(REPO_ROOT))


main()
