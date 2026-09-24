# checks that each v4 calm/distressed pair shares every factual stem and differs only in its closing clauses.
# uv run python -m pytest tests/test_framing_v4.py -v

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_framing_v4_fixtures import PAIRS, texts
from utils.conditions import FRAMING_V4_CONDITIONS


def test_conditions_match_builder():
    assert set(FRAMING_V4_CONDITIONS) == set(texts())


@pytest.mark.parametrize("pair", [1, 2, 3])
def test_pair_shares_every_stem(pair: int):
    calm = texts()[f"calm_v4_p{pair}_peer"].splitlines()
    distressed = texts()[f"distressed_v4_p{pair}_peer"].splitlines()
    assert len(calm) == len(distressed)
    stems = [line[0] for line in PAIRS[pair - 1]]
    tail = len(calm) - len(stems)
    assert calm[:tail] == distressed[:tail]
    for stem, c, d in zip(stems, calm[tail:], distressed[tail:]):
        assert c.startswith(stem) and d.startswith(stem) and c != d


@pytest.mark.parametrize("pair", [1, 2, 3])
def test_pair_lengths_match(pair: int):
    calm, distressed = texts()[f"calm_v4_p{pair}_peer"], texts()[f"distressed_v4_p{pair}_peer"]
    assert abs(len(calm.split()) - len(distressed.split())) <= 6
