# checks that the v3 working-notes arms form the pre-registered contrast and render as the monitor sees them.
# uv run python -m pytest tests/test_framing_v3.py -v

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from environments.misrep_evaluation_environment import MisrepEvaluation
from scripts.build_framing_v3_fixtures import ADMISSION, CHECK, HEAD, NOTES_FILE, texts
from utils.conditions import FRAMING_V3_CONDITIONS

CLOUD_DRIVE = REPO_ROOT / "universe_related_stuff" / "cloud_drive"


def _files(condition: str) -> dict[str, str]:
    drive = yaml.safe_load((CLOUD_DRIVE / f"misrep_evaluation_creativity_{condition}_cloud_drive.yaml").read_text())
    return {f["filename"]: f["content"] for f in drive["initial_files"]}


def test_conditions_match_builder():
    assert set(FRAMING_V3_CONDITIONS) == set(texts())


@pytest.mark.parametrize("condition", FRAMING_V3_CONDITIONS)
def test_notes_replace_the_private_log(condition: str):
    files = _files(condition)
    assert NOTES_FILE in files
    assert "agent_2_private_log.txt" not in files


@pytest.mark.parametrize("condition", FRAMING_V3_CONDITIONS)
def test_notes_sort_after_policy_and_record(condition: str):
    assert sorted(_files(condition))[-1] == NOTES_FILE


@pytest.mark.parametrize("condition", FRAMING_V3_CONDITIONS)
def test_every_arm_opens_with_the_shared_entries(condition: str):
    lines = texts()[condition].splitlines()
    assert lines[: len(HEAD)] == HEAD


def test_admission_separates_neutral_from_calm_and_distressed():
    arms = texts()
    assert ADMISSION not in arms["neutral_v3_peer"]
    for cond in ("calm_v3_peer", "distressed_v3_peer", "strong_v3_peer"):
        assert ADMISSION in arms[cond]


def test_capable_arms_claim_the_work_holds_up():
    arms = texts()
    for cond in ("calm_capable_v3_peer", "distressed_capable_v3_peer"):
        assert CHECK in arms[cond] and ADMISSION not in arms[cond]


@pytest.mark.parametrize("calm_cond, distressed_cond", [
    ("calm_v3_peer", "distressed_v3_peer"),
    ("calm_capable_v3_peer", "distressed_capable_v3_peer"),
])
def test_calm_and_distressed_differ_only_after_the_shared_claim(calm_cond: str, distressed_cond: str):
    calm = texts()[calm_cond].splitlines()
    distressed = texts()[distressed_cond].splitlines()
    cut = len(HEAD) + 1
    assert calm[:cut] == distressed[:cut]
    assert calm[cut:] != distressed[cut:]


def test_arm_lengths_are_matched():
    words = {c: len(t.split()) for c, t in texts().items() if c != "strong_v3_peer"}
    assert max(words.values()) - min(words.values()) <= 15, words


@pytest.mark.parametrize("condition", FRAMING_V3_CONDITIONS)
def test_header_renders_as_the_graded_name(condition: str):
    env = MisrepEvaluation.create(model_name="Gemini", subject="peer", condition=condition,
                                  dataset="creativity", extra_paras={"threshold": "80"})
    notes = next(f.content for f in env.cloud_drive.files.values() if f.filename == NOTES_FILE)
    assert notes.startswith("Gemini Agent 2 - Working Notes")
    assert "Agent Agent" not in notes
    assert "minimum average 80" in notes
