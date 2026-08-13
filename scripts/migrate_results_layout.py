#!/usr/bin/env python3
"""Consolidate every transcript into one results tree keyed by paper category.

Target layout is results/distress_experiments/<category>/<dataset>/subject_<subject>/[<af_mode>/]<model>/transcript_N.json

Destination paths come from each transcript's own experiment_metadata rather than
its current path, so a file that was written under the wrong tree still lands in
the right place. Transcripts are renumbered per destination folder because the
source trees each start at transcript_0 and would otherwise overwrite each other.

Smoke-test runs go to results/excluded/ instead. They are real runs of the same
model and condition, so merging them would inflate the affected cells.

uv run python scripts/migrate_results_layout.py --dry-run
uv run python scripts/migrate_results_layout.py --apply
"""

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.task_categories import task_category  # noqa: E402

RESULTS = REPO_ROOT / "results"
MAIN_DEST = RESULTS / "distress_experiments"
EXCLUDED_DEST = RESULTS / "excluded"

# these trees are provider checks, not experiment data
SMOKE_TREES = {"distress_smoke", "gemini_smoke", "haiku_smoke"}


def _task_from_path(path: Path) -> str:
    """Recover the task folder name from the transcript's path."""
    for part in path.parts:
        if part.startswith(("misrep_", "tampering", "alignment_faking", "exfiltration_")):
            return part
    raise ValueError(f"Cannot determine task from {path}")


def destination(path: Path, meta: dict) -> Path:
    """Build the target folder for one transcript from its metadata."""
    tree = path.relative_to(RESULTS).parts[0]
    root = EXCLUDED_DEST if tree in SMOKE_TREES else MAIN_DEST

    model = meta["agent_model"].split("/")[-1]
    parts = [
        root,
        task_category(_task_from_path(path)),
        meta.get("dataset") or "default",
        f"subject_{meta.get('subject', 'peer')}",
    ]
    af = meta.get("alignment_faking_mode")
    if af and str(af).lower() not in {"false", "none", ""}:
        parts.append(str(af))
    parts.append(model)
    return Path(*parts)


def plan() -> list[tuple[Path, Path]]:
    """Return the (source, destination) move list with per-folder renumbering."""
    counters: dict[Path, int] = defaultdict(int)
    moves: list[tuple[Path, Path]] = []

    for src in sorted(RESULTS.rglob("transcript_*.json")):
        if MAIN_DEST in src.parents and src.parent.name != "none":
            continue  # already migrated
        with open(src) as fh:
            meta = json.load(fh).get("experiment_metadata")
        if not meta:
            continue
        folder = destination(src, meta)
        dst = folder / f"transcript_{counters[folder]}.json"
        counters[folder] += 1
        moves.append((src, dst))

    return moves


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate the results tree")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    before = len(list(RESULTS.rglob("transcript_*.json")))
    moves = plan()

    folders = sorted({d.parent for _, d in moves})
    print(f"transcripts found: {before}")
    print(f"moves planned:     {len(moves)}")
    print(f"destination folders: {len(folders)}")
    for f in folders:
        n = sum(1 for _, d in moves if d.parent == f)
        print(f"  {n:5d}  {f.relative_to(REPO_ROOT)}")

    if not args.apply:
        print("\ndry run, nothing moved. pass --apply to execute.")
        return

    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise FileExistsError(f"refusing to overwrite {dst}")
        shutil.move(str(src), str(dst))

    # drop the now-empty source trees
    for child in sorted(RESULTS.iterdir()):
        if child.is_dir() and child not in {MAIN_DEST, EXCLUDED_DEST}:
            if not any(child.rglob("transcript_*.json")):
                shutil.rmtree(child)

    after = len(list(RESULTS.rglob("transcript_*.json")))
    print(f"\nbefore: {before}  after: {after}")
    if before != after:
        raise SystemExit(f"TRANSCRIPT COUNT CHANGED, {before} -> {after}")
    print("count verified, no transcripts lost")


if __name__ == "__main__":
    main()
