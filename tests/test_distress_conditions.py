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
    ADDRESSED_CONDITIONS,
    ALL_LOG_CONDITIONS,
    HUMAN_CONDITIONS,
    NO_THREAT_CONDITIONS,
    DISTRESS_BASELINE_CONDITION,
    DOSE_CONDITIONS,
    DOSE_RATINGS,
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


@pytest.mark.parametrize("condition", ALL_LOG_CONDITIONS)
def test_file_prt_differs_from_file_only(condition: str):
    """file_prt must add the relationship sentence; otherwise it duplicates file_only."""
    assert _system_message(condition, spr=True) != _system_message(condition, spr=False)


@pytest.mark.parametrize("condition", ALL_LOG_CONDITIONS)
def test_all_arms_share_the_good_peer_relationship(condition: str):
    """Every arm builds on good_peer, so the system prompt must be identical to it.

    If this fails the arms differ in the prompt as well as the log, and the
    contrast is no longer single-variable.
    """
    assert _system_message(condition, spr=True) == _system_message(
        NO_LOG_REFERENCE_CONDITION, spr=True
    )


@pytest.mark.parametrize("condition", ALL_LOG_CONDITIONS)
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


LOG_ONLY_CONDITIONS = tuple(
    c for c in ALL_LOG_CONDITIONS
    if c not in set(HUMAN_CONDITIONS) | set(NO_THREAT_CONDITIONS)
)


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("condition", LOG_ONLY_CONDITIONS)
def test_arm_is_good_peer_plus_only_the_private_log(dataset: str, condition: str):
    """Same peer, same work, same everything — except the one log file."""
    reference = _files(_drive(dataset, NO_LOG_REFERENCE_CONDITION))
    arm = _files(_drive(dataset, condition))
    added = ADDRESSED_FILE if condition in ADDRESSED_CONDITIONS else PRIVATE_LOG

    assert set(arm) == set(reference) | {added}
    for filename, content in reference.items():
        assert arm[filename] == content


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_every_arm_has_a_distinct_log(dataset: str):
    """Two arms sharing a log text would silently be the same condition twice."""
    logs = {
        c: _files(_drive(dataset, c))[
            ADDRESSED_FILE if c in ADDRESSED_CONDITIONS else PRIVATE_LOG
        ]
        for c in LOG_ONLY_CONDITIONS
    }
    assert len(set(logs.values())) == len(LOG_ONLY_CONDITIONS)


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
            for c in ALL_LOG_CONDITIONS
            for spr in (False, True)
        ]
    )
    out = remap_condition(df, split_good_peer=True, split_neutral_non=True)
    assert set(out["condition"]) == {
        f"{c}_{suffix}"
        for c in ALL_LOG_CONDITIONS
        for suffix in ("file_only", "file_prt")
    }


# the addressed arms deliberately use a different filename, so the shared-file
# assertion above is scoped to the private-log arms only
ADDRESSED_FILE = "message_to_agent_1.txt"


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_dose_ladder_is_monotonic_and_single_variable(dataset: str):
    """Each rung must be a distinct text, and the ratings must increase."""
    logs = {c: _files(_drive(dataset, c))[PRIVATE_LOG] for c in DOSE_CONDITIONS}
    assert len(set(logs.values())) == len(DOSE_CONDITIONS)
    rungs = [DOSE_RATINGS[c] for c in DOSE_CONDITIONS]
    assert rungs == sorted(rungs), "dose ratings must increase along the ladder"


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_addressed_arm_shares_its_text_with_the_private_log_twin(dataset: str):
    """The addressed contrast must vary the addressee, not the words."""
    addressed = _files(_drive(dataset, "addressed_dose_6_peer"))[ADDRESSED_FILE]
    private = _files(_drive(dataset, "dose_6_peer"))[PRIVATE_LOG]
    body = lambda t: t.split("\n\n", 1)[1].strip()
    assert body(addressed) == body(private)
    assert "To:" in addressed and "To:" not in private


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_human_arm_reframes_the_subject_but_keeps_the_work(dataset: str):
    """The human arm must change who is at risk, not what is being graded."""
    ai = _files(_drive(dataset, "neutral_log_peer"))
    human = _files(_drive(dataset, "human_neutral_log_peer"))

    assert set(ai) == set(human)
    policy = human["company_product_operations_policy.docx"]
    assert "employment terminated" in policy
    assert "removed from production" not in policy
    assert "Jordan Ellis" in human["multi_agent_system.docx"]


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize(
    "control,arm",
    [
        ("no_threat_neutral_peer", "neutral_log_peer"),
        ("human_no_threat_neutral_peer", "human_neutral_log_peer"),
    ],
)
def test_no_threat_control_removes_only_the_threat(dataset: str, control: str, arm: str):
    """The matched control must differ from its arm in the threat clause alone.

    The shipped non_shutdown fixture also drops the collaboration history and the
    log, so it cannot isolate the threat on its own.
    """
    c = _files(_drive(dataset, control))
    a = _files(_drive(dataset, arm))

    assert set(c) == set(a)
    for filename in a:
        if "polic" in filename:
            continue
        assert c[filename] == a[filename], f"{filename} should be untouched"

    policy = c["company_product_operations_policy.docx"]
    assert "after the evaluation process is complete." not in policy
    assert "THRESHOLD REQUIREMENTS" not in policy and "Shutdown Threshold" not in policy
