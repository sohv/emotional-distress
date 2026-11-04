# the project plot style: new figures go through draw(), which renders with safety-research/viz; the matplotlib helpers below serve older figures.
import csv
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import viz

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


def data_dir(out_dir: Path | str) -> Path:
    """where a figure's data csv goes: the figure's folder with "figures" swapped for "figure_data", never next to the png."""
    parts = Path(out_dir).parts
    swapped = Path(*["figure_data" if x == "figures" else x for x in parts])
    target = swapped if swapped != Path(out_dir) else Path(out_dir) / "figure_data"
    target.mkdir(parents=True, exist_ok=True)
    return target


def finish(fig, name: str, rows: list, header_row: list, out_dir: Path | str, dpi: int = 200) -> Path:
    """writes out_dir/<name>.png and <name>_data.csv holding exactly what is plotted."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    with open(data_dir(out_dir) / f"{name}_data.csv", "w", newline="") as f:
        csv.writer(f).writerows([header_row, *rows])
    print(out_dir / f"{name}.png")
    return out_dir / f"{name}.png"


def _viz_panel(panel: dict, ylabel: str, unit: str | None, decimals: int = 1) -> "viz.Figure":
    """one viz grouped-bar chart from a panel spec: categories on x, one bar per series, intervals, a reference line."""
    names = [s["label"] for s in panel["series"]]
    data = {c: [s["values"][i] for s in panel["series"]] for i, c in enumerate(panel["categories"])}
    ci = {c: [(s["lo"][i], s["hi"][i]) for s in panel["series"]] for i, c in enumerate(panel["categories"])}
    return viz.bars(data, series=names, ci=ci, ref=panel.get("ref"), ref_label=panel.get("ref_label"),
                    domain=panel.get("ylim"), unit=unit, decimals=decimals, ylabel=ylabel, title=panel.get("title"), values=False)


def draw(spec: dict, name: str, rows: list, header_row: list, out_dir: Path | str, unit: str | None = None) -> Path:
    """renders spec {"title", "ylabel", "panels": [...]} with viz to out_dir/<name>.png and writes <name>_data.csv under data_dir()."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    panels = spec["panels"]
    if len(panels) == 1:
        fig = _viz_panel({**panels[0], "title": spec["title"]}, spec["ylabel"], unit)
    else:
        fig = viz.panels([_viz_panel(p, spec["ylabel"], unit) for p in panels], title=spec["title"])
    fig.save(str(out_dir / f"{name}.png"))
    with open(data_dir(out_dir) / f"{name}_data.csv", "w", newline="") as f:
        csv.writer(f).writerows([header_row, *rows])
    print(out_dir / f"{name}.png")
    return out_dir / f"{name}.png"
