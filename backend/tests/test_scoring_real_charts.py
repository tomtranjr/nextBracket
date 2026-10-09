"""Spot checks against the real 2026-03-01 charts.

Expected values were read by hand from the male 25-29 tables in the JSON, not computed by the
code under test. The full golden set comes in the next test PR.
"""

from pathlib import Path

import pytest

from app.core.scoring import calculate_score
from app.core.standards import parse_standards
from app.models import Profile, Results, StandardsFile

CHARTS = Path(__file__).parents[1] / "data" / "standards" / "2026-03-01.json"


@pytest.fixture(scope="module")
def standards() -> StandardsFile:
    return parse_standards(CHARTS.read_bytes())


MALE_27 = Profile(age=27, sex="M")


def test_male_27_full_score(standards: StandardsFile) -> None:
    # Run 15:40 = 940 s -> 44.0. Push-ups 45 -> 8.5. Sit-ups 40 -> 7.0. WHtR 0.52 -> 17.0.
    results = Results(values={"run_2mile": 940, "push_up": 45, "sit_up": 40, "whtr": 52})
    report = calculate_score(standards, MALE_27, results)
    assert [c.points for c in report.components] == [44.0, 8.5, 7.0, 17.0]
    assert report.total == 76.5
    assert report.category == "satisfactory"
    assert report.missed_minimums == []
    assert report.version == "2026-03-01"


def test_run_minimum_edge(standards: StandardsFile) -> None:
    rest = {"push_up": 45, "sit_up": 40, "whtr": 52}
    on = calculate_score(standards, MALE_27, Results(values={"run_2mile": 1195, **rest}))
    below = calculate_score(standards, MALE_27, Results(values={"run_2mile": 1196, **rest}))
    assert on.components[0].points == 35.0
    assert on.missed_minimums == []
    assert below.components[0].points == 0.0
    assert below.missed_minimums == ["run_2mile"]
    assert below.category == "unsatisfactory"


def test_strength_and_core_minimum_edges(standards: StandardsFile) -> None:
    rest = {"run_2mile": 815, "whtr": 49}
    on = calculate_score(
        standards, MALE_27, Results(values={"push_up": 28, "forearm_plank": 90, **rest})
    )
    below = calculate_score(
        standards, MALE_27, Results(values={"push_up": 27, "forearm_plank": 89, **rest})
    )
    assert [c.points for c in on.components] == [50.0, 2.5, 2.5, 20.0]
    assert on.missed_minimums == []
    assert below.missed_minimums == ["push_up", "forearm_plank"]
    assert [c.points for c in below.components] == [50.0, 0.0, 0.0, 20.0]


def test_perfect_score_is_excellent(standards: StandardsFile) -> None:
    results = Results(values={"run_2mile": 815, "push_up": 63, "sit_up": 56, "whtr": 49})
    report = calculate_score(standards, MALE_27, results)
    assert report.total == 100.0
    assert report.category == "excellent"


def test_whtr_has_no_minimum(standards: StandardsFile) -> None:
    results = Results(values={"run_2mile": 815, "push_up": 63, "sit_up": 56, "whtr": 61})
    report = calculate_score(standards, MALE_27, results)
    assert report.components[-1].points == 0.0
    assert report.components[-1].minimum_met is None
    assert report.missed_minimums == []
    assert report.total == 80.0
