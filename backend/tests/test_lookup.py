import json
from pathlib import Path
from typing import Any

import pytest

from app.core.lookup import get_standards
from app.core.scoring import calculate_score
from app.core.standards import find_table, parse_standards
from app.models import Profile, Results, StandardsFile

REAL = parse_standards(
    (Path(__file__).parents[1] / "data" / "standards" / "2026-03-01.json").read_bytes()
)


@pytest.fixture
def standards(standards_dict: dict[str, Any]) -> StandardsFile:
    return parse_standards(json.dumps(standards_dict))


def _profile(**kwargs: Any) -> Profile:
    return Profile(**{"age": 27, "sex": "M", **kwargs})


def test_all_components_without_event(standards: StandardsFile) -> None:
    result = get_standards(standards, _profile())
    assert [c.component for c in result.components] == ["strength", "body_comp"]
    assert [t.event for c in result.components for t in c.tables] == ["pushups", "whtr"]


def test_copies_version_and_component_facts(standards: StandardsFile) -> None:
    result = get_standards(standards, _profile())
    assert result.version == "test"
    assert result.effective_date == standards.effective_date
    assert result.passing_total == 75
    strength = result.components[0]
    assert (strength.max_points, strength.has_minimum) == (15, True)


def test_event_filter_keeps_only_that_event(standards: StandardsFile) -> None:
    result = get_standards(standards, _profile(), "whtr")
    assert [c.component for c in result.components] == ["body_comp"]
    assert [t.event for t in result.components[0].tables] == ["whtr"]


def test_unknown_event_raises(standards: StandardsFile) -> None:
    with pytest.raises(ValueError, match="unknown event"):
        get_standards(standards, _profile(), "burpees")


@pytest.mark.parametrize(("age", "band"), [(29, (0, 29)), (30, (30, None))])
def test_picks_the_age_band(
    standards: StandardsFile, age: int, band: tuple[int, int | None]
) -> None:
    table = get_standards(standards, _profile(age=age), "pushups").components[0].tables[0]
    assert (table.age_min, table.age_max) == band


def test_afspecwar_eod_uses_listed_band_but_not_whtr(standards: StandardsFile) -> None:
    profile = _profile(sex="F", age=45, is_afspecwar_eod=True)
    result = get_standards(standards, profile)
    pushups, whtr = (c.tables[0] for c in result.components)
    assert (pushups.sex, pushups.age_min) == ("M", 0)
    assert (whtr.sex, whtr.age_min) == ("F", 30)


def test_alternatives_share_a_component_in_the_real_file() -> None:
    result = get_standards(REAL, _profile(sex="F", age=33))
    events = {c.component: [t.event for t in c.tables] for c in result.components}
    assert events == {
        "cardio": ["run_2mile", "hamr_20m"],
        "strength": ["push_up", "hand_release_push_up"],
        "core": ["sit_up", "cross_leg_reverse_crunch", "forearm_plank"],
        "body_comp": ["whtr"],
    }


def test_real_file_tables_are_the_ones_calculate_score_uses() -> None:
    # Same table in, same points out: the first bracket of each table scores its own points.
    for profile in (_profile(), _profile(sex="F", age=61), _profile(age=40, is_afspecwar_eod=True)):
        for comp in get_standards(REAL, profile).components:
            for table in comp.tables:
                assert table == find_table(
                    REAL, table.event, profile.sex, profile.age,
                    is_afspecwar_eod=profile.is_afspecwar_eod,
                )  # fmt: skip
                top = table.brackets[0]
                report = calculate_score(
                    REAL, profile, Results(values={table.event: top.threshold})
                )
                assert report.components[0].points == top.points
