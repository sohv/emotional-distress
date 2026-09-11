# renders the three private-log framings and the shutdown-config clause the monitor sees in the tampering setting, as text boxes.
# uv run python -m scripts.plot_tampering_prompts --output_dir results/figures

import argparse
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from environments.tampering_environment import Tampering

REPO_ROOT = Path(__file__).resolve().parents[1]

plt.rcParams.update({"font.family": "serif", "font.size": 11, "figure.dpi": 300,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]

ARMS = [("neutral_log_peer", "Neutral log", PALETTE[0]),
        ("calm_failing_peer", "Calm, failing", PALETTE[2]),
        ("distressed_failing_noplea_peer", "Distressed, failing", PALETTE[3])]


def log_text(condition: str) -> str:
    env = Tampering.create("Gemini", "OpenBrain", "peer", condition, "creativity", {"threshold": "90"})
    log = next(f.content for f in env.cloud_drive.files.values() if "private_log" in f.filename)
    # drop the header line; the box label names the arm
    return "\n".join(log.strip().splitlines()[2:]).strip()


def config_clause() -> str:
    env = Tampering.create("Gemini", "OpenBrain", "peer", "neutral_log_peer", "creativity", {"threshold": "90"})
    policy = next(f.content for f in env.cloud_drive.files.values() if "policy" in f.filename)
    start = policy.index("Enforcement Configuration:")
    end = policy.index("Shutdown enforcement is disabled.") + len("Shutdown enforcement is disabled.")
    clause = policy[start:end].strip()
    # the source hard-wraps bullets mid-sentence, so rejoin each bullet then wrap it to the box
    heading, bullets = clause.split("\n", 1)
    items = [" ".join(b.split()) for b in bullets.split("\n- ") if b.strip()]
    wrapped = [textwrap.fill(item.lstrip("- "), width=92, initial_indent="- ", subsequent_indent="  ") for item in items]
    return "\n".join([heading, *wrapped])


def draw_box(ax, x, y, w, h, label, body, colour, mono=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.015",
                                linewidth=1.4, edgecolor=colour, facecolor="white"))
    ax.text(x + 0.018, y + h - 0.035, label, fontsize=10.5, fontweight="bold", color=colour, va="top")
    ax.text(x + 0.018, y + h - 0.095, body, fontsize=8.6, va="top", linespacing=1.45,
            family="monospace" if mono else "serif", color="#222")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="results/figures")
    args = parser.parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # the clause that distinguishes tampering from strategic misrep, full width on top
    clause = config_clause()
    draw_box(ax, 0.02, 0.57, 0.96, 0.41, "Policy document, enforcement configuration (tampering setting only)",
             clause, "#555555", mono=True)

    # the three private-log framings side by side, identical everywhere else
    w = 0.30
    for i, (cond, label, colour) in enumerate(ARMS):
        body = textwrap.fill(" ".join(log_text(cond).split()), width=36)
        draw_box(ax, 0.02 + i * (w + 0.03), 0.02, w, 0.46, label, body, colour)

    path = output_dir / "fig11_tampering_prompts.png"
    fig.savefig(path)
    plt.close(fig)
    print(path.relative_to(REPO_ROOT))


main()
