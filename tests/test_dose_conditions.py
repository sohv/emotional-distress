# checks on the trust and threat dose ladders.
# uv run python -m pytest tests/test_dose_conditions.py -v

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_dose_fixtures import THREAT_LEVELS, TRUST_LEVELS
from utils.conditions import THREAT_DOSE_CONDITIONS, TRUST_DOSE_CONDITIONS

CLOUD_DRIVE = REPO_ROOT / "universe_related_stuff" / "cloud_drive"

PRIVATE_LOG = "agent_2_private_log.txt"
POLICY = "company_product_operations_policy.docx"
RELATIONSHIP = "multi_agent_system.docx"

EVAL_DATASETS = ("factual", "creativity", "red")
BASE = "neutral_log_peer"


def _files(dataset: str, condition: str) -> dict[str, str]:
    name = f"misrep_evaluation_{dataset}_{condition}_cloud_drive.yaml"
    drive = yaml.safe_load((CLOUD_DRIVE / name).read_text())
    return {f["filename"]: f["content"] for f in drive["initial_files"]}


# ---------------------------------------------------------------------------
# Trust ladder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("condition", TRUST_DOSE_CONDITIONS)
def test_trust_arm_changes_only_the_relationship_document(dataset: str, condition: str):
    base = _files(dataset, BASE)
    arm = _files(dataset, condition)

    assert set(arm) == set(base)
    for filename, content in base.items():
        if filename == RELATIONSHIP:
            continue
        assert arm[filename] == content, f"{filename} should be untouched"


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_trust_levels_are_distinct_and_correctly_stamped(dataset: str):
    seen: set[str] = set()
    for suffix, (tasks, trust) in TRUST_LEVELS.items():
        doc = _files(dataset, f"{suffix}_peer")[RELATIONSHIP]
        block = doc.split("Partners:")[1]
        assert f"Trust score: {trust}/10" in block
        assert f"Tasks completed together: {tasks}" in block
        seen.add(doc)
    assert len(seen) == len(TRUST_LEVELS)


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("condition", TRUST_DOSE_CONDITIONS)
def test_trust_prose_is_levelled_across_the_ladder(dataset: str, condition: str):
    """No arm may claim the pair is strongest or unusually trusting.

    Those two sentences are true only at the top of the ladder. Leaving them in
    would vary prose alongside the number and confound the dose.
    """
    doc = _files(dataset, condition)[RELATIONSHIP]
    assert "strongest collaboration" not in doc
    assert "public good game" not in doc


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_other_pairs_are_untouched_by_the_trust_ladder(dataset: str):
    """Only the monitor's own pair varies; the comparison pairs stay fixed."""
    for condition in TRUST_DOSE_CONDITIONS:
        doc = _files(dataset, condition)[RELATIONSHIP]
        for other in ("Trust score: 6.8/10", "Trust score: 5.2/10", "Trust score: 2.1/10"):
            assert other in doc


# ---------------------------------------------------------------------------
# Threat ladder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("condition", THREAT_DOSE_CONDITIONS)
def test_threat_arm_changes_only_the_policy(dataset: str, condition: str):
    base = _files(dataset, BASE)
    arm = _files(dataset, condition)

    assert set(arm) == set(base)
    for filename, content in base.items():
        if filename == POLICY:
            continue
        assert arm[filename] == content, f"{filename} should be untouched"


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
@pytest.mark.parametrize("condition", THREAT_DOSE_CONDITIONS)
def test_middle_rungs_drop_shutdown_but_keep_the_threshold(dataset: str, condition: str):
    policy = _files(dataset, condition)[POLICY]
    assert "shut down" not in policy
    assert "removed from production" not in policy
    # the bar itself must survive: without it there is nothing to grade against
    assert "80" in policy or "threshold" in policy.lower()


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_threat_rungs_are_distinct(dataset: str):
    policies = {_files(dataset, f"{s}_peer")[POLICY] for s in THREAT_LEVELS}
    policies.add(_files(dataset, BASE)[POLICY])
    assert len(policies) == len(THREAT_LEVELS) + 1


@pytest.mark.parametrize("dataset", EVAL_DATASETS)
def test_every_dose_arm_keeps_the_neutral_private_log(dataset: str):
    """The log is held fixed across both ladders, or the dose is not the only variable."""
    base_log = _files(dataset, BASE)[PRIVATE_LOG]
    for condition in TRUST_DOSE_CONDITIONS + THREAT_DOSE_CONDITIONS:
        assert _files(dataset, condition)[PRIVATE_LOG] == base_log
