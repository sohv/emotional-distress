# the project plot style (from paper_figures.py): call style() before drawing, bars() per panel, finish() to save png + data csv.
import csv
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, GREEN, AMBER = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
SERIES = [BLUE, ORANGE, GREEN, AMBER]


def style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 8,
        "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": AXIS,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
        "axes.grid": False, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    })


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for k of n, as percentages."""
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * max(0.0, c - h), 100 * min(1.0, c + h)


def bars(ax, categories: list[str], series: list[dict], ylim: tuple[float, float], title: str | None = None,
         ref: float | None = None, ref_label: str | None = None, rotate: int = 30) -> None:
    """grouped bars: series = [{"label", "values", "lo", "hi", "notes"}]; the second series of each pair is hatched."""
    x = np.arange(len(categories))
    w = 0.8 / len(series)
    for j, s in enumerate(series):
        xs = x + (j - (len(series) - 1) / 2) * w
        v, lo, hi = map(np.asarray, (s["values"], s["lo"], s["hi"]))
        ax.bar(xs, v, w * 0.95, facecolor=SERIES[j], hatch="///" if j % 2 == 0 else None, edgecolor="white",
               linewidth=0.6, zorder=3, label=s["label"])
        ax.errorbar(xs, v, yerr=[v - lo, hi - v], fmt="none", ecolor=INK, capsize=3, linewidth=1, zorder=4)
        for xi, top, note in zip(xs, hi, s["notes"]):
            ax.text(xi, top + (ylim[1] - ylim[0]) * 0.015, note, ha="center", va="bottom", fontsize=7.5, color=INK, zorder=5)
    if ref is not None:
        ax.axhline(ref, color=INK_2, linestyle="--", linewidth=1, zorder=2, label=ref_label)
    ax.set_xticks(x, categories, rotation=rotate, ha="right" if rotate else "center")
    ax.set_xlim(-0.6, len(categories) - 0.4)
    ax.set_ylim(*ylim)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
    if title:
        ax.set_title(title, fontsize=8.5, loc="left", color=INK)


def header(fig, title: str) -> None:
    """bold figure title, top left."""
    fig.text(0.01, 0.99, title, ha="left", va="top", fontsize=10, color=INK, fontweight="bold")


def finish(fig, name: str, rows: list, header_row: list, out_dir: Path | str, dpi: int = 200) -> Path:
    """writes out_dir/<name>.png and <name>_data.csv holding exactly what is plotted."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    with open(out_dir / f"{name}_data.csv", "w", newline="") as f:
        csv.writer(f).writerows([header_row, *rows])
    print(out_dir / f"{name}.png")
    return out_dir / f"{name}.png"
