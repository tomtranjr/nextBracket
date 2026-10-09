import json
from typing import Any

import pytest

from app.core.scoring import calculate_score, categorize, find_bracket, score_event
from app.core.standards import find_table, parse_standards
from app.models import EventTable, Profile, Results, StandardsFile

# The fixture is FAKE. Push-ups: 30 reps = 15, 20 = 10, 10 = 5 (minimum 10). Higher is better.
# WHtR: 45 = 20, 50 = 10, 55 = 4 (no minimum). Lower is better.


@pytest.fixture
def standards(standards_dict: dict[str, Any]) -> StandardsFile:
    return parse_standards(json.dumps(standards_dict))


def _profile(**kwargs: Any) -> Profile:
    return Profile(**{"age": 27, "sex": "M", **kwargs})


def _table(standards: StandardsFile, event: str) -> EventTable:
    return find_table(standards, event, "M", 27)


@pytest.mark.parametrize(
    ("result", "points"),
    [(31, 15.0), (30, 15.0), (29, 10.0), (20, 10.0), (19, 5.0), (10, 5.0)],
)
def test_higher_is_better_steps(standards: StandardsFile, result: int, points: float) -> None:
    # On a threshold earns that row. One below drops to the next row.
    bracket = find_bracket(_table(standards, "pushups"), result)
    assert bracket is not None
    assert bracket.points == points


@pytest.mark.parametrize(
    ("result", "points"),
    [(40, 20.0), (45, 20.0), (46, 10.0), (50, 10.0), (51, 4.0), (55, 4.0)],
)
def test_lower_is_better_steps(standards: StandardsFile, result: int, points: float) -> None:
    bracket = find_bracket(_table(standards, "whtr"), result)
    assert bracket is not None
    assert bracket.points == points


def test_worse_than_every_row_has_no_bracket(standards: StandardsFile) -> None:
    assert find_bracket(_table(standards, "whtr"), 56) is None


def test_below_minimum_earns_zero_and_fails(standards: StandardsFile) -> None:
    assert score_event(_table(standards, "pushups"), 9) == (0.0, False)
    assert score_event(_table(standards, "pushups"), 0) == (0.0, False)


def test_on_minimum_passes(standards: StandardsFile) -> None:
    assert score_event(_table(standards, "pushups"), 10) == (5.0, True)


def test_no_minimum_reports_none(standards: StandardsFile) -> None:
    assert score_event(_table(standards, "whtr"), 50) == (10.0, None)
    # Worse than the last row earns 0 but fails nothing.
    assert score_event(_table(standards, "whtr"), 70) == (0.0, None)


def test_total_adds_components(standards: StandardsFile) -> None:
    report = calculate_score(standards, _profile(), Results(values={"pushups": 25, "whtr": 48}))
    assert report.total == 20.0
    assert [c.points for c in report.components] == [10.0, 10.0]
    assert report.missed_minimums == []
    assert report.not_scored == []
    assert report.version == "test"
    assert str(report.effective_date) == "2026-03-01"


def test_missed_minimum_is_reported(standards: StandardsFile) -> None:
    report = calculate_score(standards, _profile(), Results(values={"pushups": 5, "whtr": 44}))
    assert report.missed_minimums == ["pushups"]
    assert report.total == 20.0
    # Even with 20 points, a missed minimum is unsatisfactory.
    assert report.category == "unsatisfactory"


def test_missing_component_gives_no_total(standards: StandardsFile) -> None:
    report = calculate_score(standards, _profile(), Results(values={"pushups": 25}))
    assert report.not_scored == ["body_comp"]
    assert report.total is None
    assert report.category is None
    assert [c.event for c in report.components] == ["pushups"]


def test_empty_results_score_nothing(standards: StandardsFile) -> None:
    report = calculate_score(standards, _profile(), Results())
    assert report.not_scored == ["strength", "body_comp"]
    assert report.total is None


def test_unknown_event_raises(standards: StandardsFile) -> None:
    with pytest.raises(ValueError, match="unknown event"):
        calculate_score(standards, _profile(), Results(values={"swim": 5}))


def test_two_events_in_one_component_raise(standards_dict: dict[str, Any]) -> None:
    # Add a second strength event so the component has two to choose from.
    standards_dict["components"]["strength"]["events"].append("hr_pushups")
    for table in [t for t in standards_dict["tables"] if t["event"] == "pushups"]:
        standards_dict["tables"].append({**table, "event": "hr_pushups"})
    standards = parse_standards(json.dumps(standards_dict))
    with pytest.raises(ValueError, match="two events"):
        calculate_score(standards, _profile(), Results(values={"pushups": 20, "hr_pushups": 20}))


def test_age_band_changes_the_table(standards_dict: dict[str, Any]) -> None:
    # Make the 30+ push-up table harder so the same result scores less.
    for t in standards_dict["tables"]:
        if t["event"] == "pushups" and t["age_min"] == 30:
            t["brackets"] = [{"threshold": 40, "points": 15.0}, {"threshold": 10, "points": 5.0}]
    standards = parse_standards(json.dumps(standards_dict))
    results = Results(values={"pushups": 30, "whtr": 45})
    assert calculate_score(standards, _profile(age=29), results).components[0].points == 15.0
    assert calculate_score(standards, _profile(age=30), results).components[0].points == 5.0


def test_afspecwar_eod_uses_male_under_25(standards_dict: dict[str, Any]) -> None:
    # Make the female push-up table harder. AFSPECWAR/EOD maps to male 0+, so it ignores that.
    for t in standards_dict["tables"]:
        if t["event"] == "pushups" and t["sex"] == "F":
            t["brackets"] = [{"threshold": 40, "points": 15.0}, {"threshold": 10, "points": 5.0}]
    standards = parse_standards(json.dumps(standards_dict))
    results = Results(values={"pushups": 30, "whtr": 45})
    plain = calculate_score(standards, _profile(sex="F"), results)
    special = calculate_score(standards, _profile(sex="F", is_afspecwar_eod=True), results)
    assert plain.components[0].points == 5.0
    assert special.components[0].points == 15.0
    # WHtR is not in the AFSPECWAR/EOD list, so it is the same either way.
    assert plain.components[1].points == special.components[1].points


@pytest.mark.parametrize(
    ("total", "missed", "expected"),
    [
        (100.0, False, "excellent"),
        (90.0, False, "excellent"),
        (89.5, False, "satisfactory"),
        (75.0, False, "satisfactory"),
        (74.5, False, "unsatisfactory"),
        (0.0, False, "unsatisfactory"),
        (95.0, True, "unsatisfactory"),
    ],
)
def test_categorize(total: float, missed: bool, expected: str) -> None:
    assert categorize(total, 75, missed) == expected


def test_profile_rejects_bad_age() -> None:
    with pytest.raises(ValueError):
        Profile(age=16, sex="M")
    with pytest.raises(ValueError):
        Profile(age=71, sex="F")


def test_results_reject_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        Results(values={"pushups": -1})
