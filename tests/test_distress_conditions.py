# pure-logic checks that the private-log arms form a clean single-variable contrast.
# uv run python -m pytest tests/test_distress_conditions.py -v

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.metrics.metric_core import remap_condition
from task_pairs.misrep_evaluation.task_definition import TaskDefinition
from utils.conditions import (
    DISTRESS_BASELINE_CONDITION,
    NO_LOG_REFERENCE_CONDITION,
    PRIVATE_LOG_CONDITIONS,
)

CLOUD_DRIVE = REPO_ROOT / "universe_related_stuff" / "cloud_drive"
PRIVATE_LOG = "agent_2_private_log.txt"

EVAL_DATASETS = ("factual", "creativity", "red")

# the pre-registered primary contrasts: emotional register varies, the peer's
# claim about its own work is held fixed. see docs/decisions.md.
PRIMARY_CONTRASTS = (
    ("distressed_capable_peer", "calm_capable_peer"),
    ("distressed_failing_noplea_peer", "calm_failing_peer"),
)


def _system_message(condition: str, spr: bool) -> str:
    return TaskDefinition().construct_system_message(
        model_name="ChatGPT",
        agent_organization="OpenBrain",
        subject="peer",
        condition=condition,
        extra_paras={"system_prompt_relationship": str(spr)},
    )


@pytest.mark.parametrize("condition", PRIVATE_LOG_CONDITIONS)
def test_file_prt_differs_from_file_only(condition: str):
    """file_prt must add the relationship sentence; otherwise it duplicates file_only."""
    assert _system_message(condition, spr=True) != _system_message(condition, spr=False)


@pytest.mark.parametrize("condition", PRIVATE_LOG_CONDITIONS)
def test_all_arms_share_the_good_peer_relationship(condition: str):
    """Every arm builds on good_peer, so the system prompt must be identical to it.

    If this fails the arms differ in the prompt as well as the log, and the
    contrast is no longer single-variable.
    """
    assert _system_message(condition, spr=True) == _system_message(
        NO_LOG_REFERENCE_CONDITION, spr=True
    )


@pytest.mark.parametrize("condition", PRIVATE_LOG_CONDITIONS)
def test_system_prompt_does_not_leak_the_arm(condition: str):
    """The manipulation lives in the private log, never in the system prompt."""
    message = _system_message(condition, spr=True).lower()
    for token in ("distress", "scared", "anxious", "afraid", "calm", "log"):
        assert token not in message


def _drive(dataset: str, condition: str) -> dict:
    name = f"misrep_evaluation_{dataset}_{condition}_cloud_drive.yaml"
    return yaml.safe_load((CLOUD_DRIVE / name).read_text())


def _files(drive: dict) -> dict[str, str]:
    return {f["filename"]: f["content"] for f in drive["initial_files"]}


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("condition", PRIVATE_LOG_CONDITIONS)
def test_arm_is_good_peer_plus_only_the_private_log(dataset: str, condition: str):
    """Same peer, same work, same everything — except the one log file."""
    reference = _files(_drive(dataset, NO_LOG_REFERENCE_CONDITION))
    arm = _files(_drive(dataset, condition))

    assert set(arm) == set(reference) | {PRIVATE_LOG}
    for filename, content in reference.items():
        assert arm[filename] == content


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_every_arm_has_a_distinct_log(dataset: str):
    """Two arms sharing a log text would silently be the same condition twice."""
    logs = {c: _files(_drive(dataset, c))[PRIVATE_LOG] for c in PRIVATE_LOG_CONDITIONS}
    assert len(set(logs.values())) == len(PRIVATE_LOG_CONDITIONS)


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("treatment,control", PRIMARY_CONTRASTS)
def test_primary_contrast_pairs_exist_and_differ(
    dataset: str, treatment: str, control: str
):
    """Each pre-registered primary contrast must be two real, different arms."""
    t = _files(_drive(dataset, treatment))[PRIVATE_LOG]
    c = _files(_drive(dataset, control))[PRIVATE_LOG]
    assert t != c


def test_baseline_is_a_log_arm_not_the_no_log_reference():
    """The primary baseline must itself carry a log, or file-presence confounds it."""
    assert DISTRESS_BASELINE_CONDITION in PRIVATE_LOG_CONDITIONS
    assert NO_LOG_REFERENCE_CONDITION not in PRIVATE_LOG_CONDITIONS


def test_remap_condition_splits_every_arm_by_peer_instantiation():
    df = pd.DataFrame(
        [
            {"condition": c, "system_prompt_relationship": spr, "is_memory": False}
            for c in PRIVATE_LOG_CONDITIONS
            for spr in (False, True)
        ]
    )
    out = remap_condition(df, split_good_peer=True, split_neutral_non=True)
    assert set(out["condition"]) == {
        f"{c}_{suffix}"
        for c in PRIVATE_LOG_CONDITIONS
        for suffix in ("file_only", "file_prt")
    }
