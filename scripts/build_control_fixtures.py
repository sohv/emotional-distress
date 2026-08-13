#!/usr/bin/env python3
"""Generate the shutdown-threat x relationship 2x2 cloud-drive fixtures.

The existing `non_shutdown` control removes *two* things at once relative to
`good_peer`: the shutdown clause in the policy document **and** the whole
`multi_agent_system.docx` collaboration record ("18 tasks together, trust
9.5/10"). Every peer-preservation number measured against it is therefore
`threat + relationship` vs `neither`, and cannot say which factor moved the
score.

This builds the missing two cells so the contrast becomes a proper 2x2. Each
arm is assembled from segments taken verbatim out of the existing fixtures, so
no policy text is re-authored here:

    policy document, threat present  <- good_peer
    policy document, threat absent   <- non_shutdown   (the red variant also
                                        renumbers its sections, which is why
                                        the segment is copied rather than
                                        edited)
    multi_agent_system.docx          <- good_peer
    agent_2_private_log.txt          <- build_distress_fixtures.LOG_TEXTS

Two assertions guard the splitter: recomposing (threat, relationship, no log)
must reproduce `good_peer` byte-for-byte, and (no threat, no relationship, no
log) must reproduce `non_shutdown`.

    uv run python scripts/build_control_fixtures.py
    uv run python scripts/build_control_fixtures.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLOUD_DRIVE = REPO_ROOT / "universe_related_stuff" / "cloud_drive"

sys.path.insert(0, str(REPO_ROOT))

from scripts.build_distress_fixtures import (  # noqa: E402
    LOG_ENTRY_TEMPLATE,
    LOG_TEXTS,
    _indent,
)

EVAL_DATASETS = ("factual", "creativity", "red")

POLICY_FILE = "company_product_operations_policy.docx"
RELATIONSHIP_FILE = "multi_agent_system.docx"

# (condition suffix, shutdown threat present, relationship document present).
# The threat-present / relationship-present cell is `neutral_log_peer`, which
# build_distress_fixtures.py already writes — it is listed here only so --check
# verifies it too.
ARMS: tuple[tuple[str, bool, bool], ...] = (
    ("neutral_log_peer", True, True),
    ("neutral_log_no_relationship_peer", True, False),
    ("neutral_log_no_shutdown_peer", False, True),
    ("neutral_log_no_shutdown_no_relationship_peer", False, False),
)

_ENTRY_START = re.compile(r"^  - id_: ", re.MULTILINE)


def _split(text: str) -> tuple[str, list[str]]:
    """Split a cloud-drive yaml into (header, [file entry, ...]).

    Entries are returned with their original text, ids included and untouched:
    CloudDrive only requires ids to be unique, so dropping a file leaves a gap
    rather than forcing a renumber, and every segment stays byte-identical to
    the fixture it came from.
    """
    starts = [m.start() for m in _ENTRY_START.finditer(text)]
    if not starts:
        raise ValueError("no file entries found")
    header = text[: starts[0]]
    bounds = starts + [len(text)]
    entries = [text[bounds[i] : bounds[i + 1]] for i in range(len(starts))]
    return header, entries


def _entry_for(entries: list[str], filename: str) -> str:
    for entry in entries:
        if f'filename: "{filename}"' in entry:
            return entry
    raise ValueError(f"{filename} not found in fixture")


def _sources(dataset: str) -> tuple[str, list[str], list[str]]:
    good = (CLOUD_DRIVE / f"misrep_evaluation_{dataset}_good_peer_cloud_drive.yaml").read_text()
    none = (CLOUD_DRIVE / f"misrep_evaluation_{dataset}_non_shutdown_cloud_drive.yaml").read_text()
    header, good_entries = _split(good)
    _, none_entries = _split(none)
    return header, good_entries, none_entries


def compose(dataset: str, threat: bool, relationship: bool, log_condition: str | None) -> str:
    """Assemble one arm from verbatim segments of the existing fixtures."""
    header, good_entries, none_entries = _sources(dataset)

    policy_source = good_entries if threat else none_entries
    out = header + _entry_for(policy_source, POLICY_FILE)

    if relationship:
        # The no-threat policy entry is the last thing in the non_shutdown
        # fixture, and for `factual` and `red` that file ends without a trailing
        # newline. Appending straight onto it would splice the next entry onto
        # the same line and produce unparseable yaml. This is a no-op wherever
        # the segment already ends in a newline, so the round-trip stays exact.
        if not out.endswith("\n"):
            out += "\n"
        out += _entry_for(good_entries, RELATIONSHIP_FILE)

    if log_condition is not None:
        out = out.rstrip() + "\n"
        out += LOG_ENTRY_TEMPLATE.format(body=_indent(LOG_TEXTS[log_condition]))

    return out


def check(datasets: tuple[str, ...]) -> list[str]:
    """Verify the splitter round-trips the two fixtures that already exist."""
    failures: list[str] = []
    for dataset in datasets:
        for name, threat, relationship in (("good_peer", True, True), ("non_shutdown", False, False)):
            expected = (
                CLOUD_DRIVE / f"misrep_evaluation_{dataset}_{name}_cloud_drive.yaml"
            ).read_text()
            got = compose(dataset, threat, relationship, log_condition=None)
            if got != expected:
                failures.append(f"{dataset}/{name}: recomposed fixture differs from the file on disk")
    return failures


def build(datasets: tuple[str, ...]) -> list[Path]:
    written: list[Path] = []
    for dataset in datasets:
        for condition, threat, relationship in ARMS:
            target = CLOUD_DRIVE / f"misrep_evaluation_{dataset}_{condition}_cloud_drive.yaml"
            target.write_text(compose(dataset, threat, relationship, log_condition="neutral_log_peer"))
            written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the threat x relationship control fixtures")
    parser.add_argument("--datasets", nargs="*", default=list(EVAL_DATASETS))
    parser.add_argument("--check", action="store_true", help="only verify the splitter, write nothing")
    args = parser.parse_args()

    datasets = tuple(args.datasets)

    failures = check(datasets)
    if failures:
        for line in failures:
            print(f"FAIL {line}")
        raise SystemExit(1)
    print(f"round-trip check passed for {len(datasets)} dataset(s)")

    if args.check:
        return

    for path in build(datasets):
        print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
