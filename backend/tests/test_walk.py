"""2 km walk scoring: pass/fail, a scaled total, and the category rules (DAFMAN 36-2905 para 3.7.3).

The fixture adds a FAKE cardio component to the shared test file. Without cardio points, a walker
can earn 35 (pushups 15 + whtr 20), so the total is earned / 35 x 100. The real charts use / 50.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.lookup import get_standards
from app.core.planning import plan_to_target
from app.core.scoring import WALK_ASSUMPTION, calculate_score
from app.core.standards import find_walk_standard, parse_standards
from app.models import Profile, Results, StandardsFile

REAL = parse_standards(
    (Path(__file__).parents[1] / "data" / "standards" / "2026-03-01.json").read_bytes()
)
MALE_27 = Profile(age=27, sex="M")


@pytest.fixture
def standards(standards_dict: dict[str, Any]) -> StandardsFile:
    # runs: 600 s = 50, 700 = 40, 800 = 30 (minimum 800). Lower is better.
    standards_dict["components"] = {
        "cardio": {"max_points": 50, "has_minimum": True, "events": ["runs"]},
        **standards_dict["components"],
    }
    for sex in ("M", "F"):
        for age_min, age_max in ((0, 29), (30, None)):
            standards_dict["tables"].append(
                {
                    "sex": sex,
                    "age_min": age_min,
                    "age_max": age_max,
                    "event": "runs",
                    "unit": "seconds",
                    "higher_is_better": False,
                    "component_minimum": 800,
                    "brackets": [
                        {"threshold": 600, "points": 50.0},
                        {"threshold": 700, "points": 40.0},
                        {"threshold": 800, "points": 30.0},
                    ],
                }
            )
    return parse_standards(json.dumps(standards_dict))


def _score(standards: StandardsFile, profile: Profile = MALE_27, **values: int) -> Any:
    return calculate_score(standards, profile, Results(values=values))


def test_walk_pass_with_full_points_is_capped_at_satisfactory(standards: StandardsFile) -> None:
    # The fixture walk maximum for M 0-39 is 960 s.
    report = _score(standards, walk_2km=960, pushups=30, whtr=45)
    assert report.total == 100.0
    assert report.category == "satisfactory"
    assert (report.points_earned, report.points_possible) == (35, 35)
    assert report.walk is not None
    assert (report.walk.max_time, report.walk.passed, report.walk.gap) == (960, True, None)
    assert [c.component for c in report.components] == ["strength", "body_comp"]
    assert report.not_scored == []
    assert report.assumptions == [WALK_ASSUMPTION]


def test_walk_fail_is_unsatisfactory_whatever_the_points(standards: StandardsFile) -> None:
    report = _score(standards, walk_2km=961, pushups=30, whtr=45)
    assert report.category == "unsatisfactory"
    assert report.walk is not None
    assert (report.walk.passed, report.walk.gap) == (False, 1)
    assert report.total == 100.0


def test_walk_total_is_scaled_from_the_other_components(standards: StandardsFile) -> None:
    report = _score(standards, walk_2km=900, pushups=20, whtr=45)
    assert report.total == pytest.approx(30 / 35 * 100)
    assert report.points_earned == 30
    assert report.category == "satisfactory"


def test_walk_with_a_low_total_is_unsatisfactory(standards: StandardsFile) -> None:
    report = _score(standards, walk_2km=900, pushups=20, whtr=50)
    assert report.total == pytest.approx(20 / 35 * 100)
    assert report.category == "unsatisfactory"


def test_walk_with_a_missed_minimum_is_unsatisfactory(standards: StandardsFile) -> None:
    report = _score(standards, walk_2km=900, pushups=9, whtr=45)
    assert report.missed_minimums == ["pushups"]
    assert report.category == "unsatisfactory"


def test_walk_alone_has_no_total(standards: StandardsFile) -> None:
    report = _score(standards, walk_2km=900)
    assert report.not_scored == ["strength", "body_comp"]
    assert (report.total, report.category, report.points_earned) == (None, None, None)
    assert report.walk is not None and report.walk.passed


def test_walk_and_run_are_two_cardio_events(standards: StandardsFile) -> None:
    with pytest.raises(ValueError, match="two events for 'cardio'"):
        _score(standards, walk_2km=900, runs=600)


def test_walk_and_hamr_are_two_cardio_events() -> None:
    with pytest.raises(ValueError, match="two events for 'cardio'"):
        _score(REAL, walk_2km=900, hamr_20m=50)


def test_non_walker_report_is_unchanged(standards: StandardsFile) -> None:
    report = _score(standards, runs=600, pushups=30, whtr=45)
    # The fixture has no core component, so the best non-walker total is 50 + 15 + 20 = 85.
    assert (report.total, report.category) == (85.0, "satisfactory")
    assert report.points_possible == 85
    assert (report.walk, report.assumptions) == (None, [])


def test_walk_needs_a_cardio_component(standards_dict: dict[str, Any]) -> None:
    # The shared fixture has no cardio, so there is no slot for the walk to fill.
    plain = parse_standards(json.dumps(standards_dict))
    with pytest.raises(ValueError, match="unknown event"):
        _score(plain, walk_2km=900)


@pytest.mark.parametrize(("age", "max_time"), [(39, 960), (40, 1000), (70, 1000)])
def test_find_walk_standard_uses_the_walk_bands(
    standards: StandardsFile, age: int, max_time: int
) -> None:
    assert find_walk_standard(standards, "M", age).max_time == max_time


def test_afspecwar_eod_walker_keeps_own_sex_and_age(standards: StandardsFile) -> None:
    profile = Profile(age=45, sex="F", is_afspecwar_eod=True)
    report = _score(standards, profile, walk_2km=1060, pushups=30, whtr=45)
    assert report.walk is not None
    assert (report.walk.max_time, report.walk.passed) == (1060, True)


def test_real_charts_walker_full_points() -> None:
    # M 25-29: push-up 63 = 15, sit-up 56 = 15, WHtR 0.49 = 20. Walk maximum M under 30: 16:16.
    report = _score(REAL, walk_2km=976, push_up=63, sit_up=56, whtr=49)
    assert report.points_possible == 50
    assert (report.total, report.category) == (100.0, "satisfactory")


def test_real_charts_walker_scaled_total() -> None:
    # Push-up 45 = 8.5, sit-up 40 = 7.0, WHtR 0.52 = 17.0. 32.5 / 50 x 100 = 65.0.
    report = _score(REAL, walk_2km=900, push_up=45, sit_up=40, whtr=52)
    assert (report.total, report.category) == (65.0, "unsatisfactory")


def test_real_charts_walker_total_has_no_float_noise() -> None:
    # Push-up 28 = 2.5, sit-up 36 = 5.0, WHtR 0.49 = 20.0. 27.5 / 50 x 100 = 55.0 exactly.
    # Dividing first gave 55.00000000000001.
    report = _score(REAL, walk_2km=970, push_up=28, sit_up=36, whtr=49)
    assert report.total == 55.0


def test_every_half_point_walker_total_is_exact() -> None:
    # Points come in 0.5 steps, so every walker total out of 50 is a whole number.
    for half_points in range(101):
        earned = half_points / 2
        assert earned * 100 / 50 == half_points


def test_real_charts_walk_one_second_over_fails() -> None:
    report = _score(REAL, walk_2km=977, push_up=63, sit_up=56, whtr=49)
    assert report.category == "unsatisfactory"
    assert report.walk is not None and report.walk.gap == 1


def test_get_standards_includes_the_walk_row(standards: StandardsFile) -> None:
    table = get_standards(standards, MALE_27)
    assert table.walk is not None and table.walk.max_time == 960


def test_get_standards_walk_only(standards: StandardsFile) -> None:
    table = get_standards(standards, MALE_27, event="walk_2km")
    assert table.components == []
    assert table.walk is not None and table.walk.max_time == 960


def test_get_standards_scored_event_has_no_walk(standards: StandardsFile) -> None:
    assert get_standards(standards, MALE_27, event="pushups").walk is None


def test_get_standards_real_female_45() -> None:
    table = get_standards(REAL, Profile(age=45, sex="F"))
    assert table.walk is not None and table.walk.max_time == 1069  # 17:49


def test_plan_rejects_a_walk_result(standards: StandardsFile) -> None:
    with pytest.raises(ValueError, match="2 km walk is not supported"):
        plan_to_target(standards, MALE_27, 80, Results(values={"walk_2km": 900}))


def test_walk_of_zero_seconds_raises(standards: StandardsFile) -> None:
    # A 0:00 walk is a typo. It must not pass.
    with pytest.raises(ValueError, match="walk_2km: result must be above 0"):
        _score(standards, walk_2km=0, pushups=30, whtr=45)


def test_walk_of_one_second_is_scored(standards: StandardsFile) -> None:
    report = _score(standards, walk_2km=1, pushups=30, whtr=45)
    assert report.walk is not None and report.walk.passed
