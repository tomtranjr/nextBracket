import json
from pathlib import Path
from typing import Any

import pytest

from app.core.planning import plan_to_target
from app.core.scoring import calculate_score
from app.core.standards import find_table, parse_standards
from app.models import PlanResult, Profile, Results, StandardsFile

REAL = parse_standards(
    (Path(__file__).parents[1] / "data" / "standards" / "2026-03-01.json").read_bytes()
)


@pytest.fixture
def standards(standards_dict: dict[str, Any]) -> StandardsFile:
    return parse_standards(json.dumps(standards_dict))


# Fixture charts (age 27, any sex). pushups: 30 = 15, 20 = 10, 10 = 5, minimum 10.
# whtr: 45 = 20, 50 = 10, 55 = 4, no minimum. The best total is 35.
PROFILE = Profile(age=27, sex="M")


def _plan(standards: StandardsFile, target: float, **values: int) -> PlanResult:
    return plan_to_target(standards, PROFILE, target, Results(values=values))


def _by_event(plan: PlanResult) -> dict[str, tuple[int | None, int, int | None]]:
    """Map event to (from_result, to_result, delta). Each option here changes one event."""
    return {
        o.changes[0].event: (o.changes[0].from_result, o.changes[0].to_result, o.changes[0].delta)
        for o in plan.options
    }


def test_one_option_per_event_that_can_reach_the_target(standards: StandardsFile) -> None:
    plan = _plan(standards, 14, pushups=10, whtr=55)
    assert plan.status == "options"
    assert plan.current_total == 9
    # pushups to 20 gives 4 + 10 = 14. whtr to 50 gives 5 + 10 = 15.
    assert _by_event(plan) == {"pushups": (10, 20, 10), "whtr": (55, 50, -5)}
    assert [o.projected_total for o in plan.options] == [14, 15]


def test_picks_the_smallest_improvement(standards: StandardsFile) -> None:
    # whtr 50 gives 5 + 10 = 15, which is below 20. Only 45 reaches it.
    plan = _plan(standards, 20, pushups=10, whtr=55)
    assert _by_event(plan) == {"whtr": (55, 45, -10)}


def test_target_on_a_bracket_edge_counts(standards: StandardsFile) -> None:
    plan = _plan(standards, 15, pushups=10, whtr=55)
    assert plan.options[-1].projected_total == 15


def test_already_met_has_no_options(standards: StandardsFile) -> None:
    plan = _plan(standards, 35, pushups=30, whtr=45)
    assert (plan.status, plan.options) == ("already_met", [])


def test_target_above_the_best_total_is_impossible(standards: StandardsFile) -> None:
    plan = _plan(standards, 36, pushups=10, whtr=55)
    assert (plan.status, plan.max_total, plan.options) == ("impossible", 35, [])


def test_reachable_target_but_no_single_event_does_it(standards: StandardsFile) -> None:
    # pushups alone reaches 4 + 15 = 19. whtr alone reaches 5 + 20 = 25.
    plan = _plan(standards, 30, pushups=10, whtr=55)
    assert (plan.status, plan.options) == ("no_single_event_option", [])


def test_missed_minimum_must_be_fixed_even_if_total_is_met(standards: StandardsFile) -> None:
    # 5 pushups is below the minimum (0 points). The total is 20, but the member fails.
    plan = _plan(standards, 20, pushups=5, whtr=45)
    assert plan.current_total == 20
    # Only pushups can fix its own minimum. Improving whtr cannot.
    assert _by_event(plan) == {"pushups": (5, 10, 5)}


def test_never_offers_a_row_below_the_minimum(standards_dict: dict[str, Any]) -> None:
    # The real charts print no row below the minimum, but the schema allows one.
    for table in standards_dict["tables"]:
        if table["event"] == "pushups":
            table["brackets"].append({"threshold": 5, "points": 2.0})
    standards = parse_standards(json.dumps(standards_dict))
    # Total 20 already meets the target of 15, so only the minimum is in the way.
    plan = _plan(standards, 15, pushups=5, whtr=45)
    assert _by_event(plan) == {"pushups": (5, 10, 5)}


def test_no_results_plans_from_the_minimum(standards: StandardsFile) -> None:
    plan = plan_to_target(standards, PROFILE, 20)
    assert plan.assumed_components == ["strength", "body_comp"]
    # The minimum earns 5 points. Body composition starts at 0.
    assert plan.current_total == 5
    # pushups alone reaches 0 + 15. whtr alone reaches 5 + 20 at 45.
    assert _by_event(plan) == {"whtr": (None, 45, None)}


def test_negative_target_raises(standards: StandardsFile) -> None:
    with pytest.raises(ValueError, match="negative"):
        plan_to_target(standards, PROFILE, -1)


def test_unknown_event_raises(standards: StandardsFile) -> None:
    with pytest.raises(ValueError, match="unknown event"):
        _plan(standards, 20, burpees=3)


def test_copies_version_and_target(standards: StandardsFile) -> None:
    plan = _plan(standards, 14, pushups=10, whtr=55)
    assert (plan.version, plan.target, plan.effective_date) == (
        "test",
        14,
        standards.effective_date,
    )


# Property check on the real charts: the plan and `calculate_score` must agree.

# Which bracket the member sits on in each component. "below" is one step under the minimum.
PLACEMENTS = ("best", "middle", "minimum", "below")
TARGETS = (60.0, 75.0, 90.0, 100.0)


def _result_at(standards: StandardsFile, profile: Profile, event: str, placement: str) -> int:
    table = find_table(
        standards, event, profile.sex, profile.age, is_afspecwar_eod=profile.is_afspecwar_eod
    )
    brackets = table.brackets
    if placement == "best":
        return brackets[0].threshold
    if placement == "middle":
        return brackets[len(brackets) // 2].threshold
    minimum = table.component_minimum
    if minimum is None:
        # WHtR has no minimum, so its "minimum" and "below" are the last printed row.
        return brackets[-1].threshold
    if placement == "minimum":
        return minimum
    return minimum - 1 if table.higher_is_better else minimum + 1


@pytest.mark.parametrize("sex", ["M", "F"])
@pytest.mark.parametrize("age", [17, 24, 25, 33, 47, 60, 70])
@pytest.mark.parametrize("is_afspecwar_eod", [False, True])
def test_every_option_reaches_the_target_and_is_minimal(
    sex: Any, age: int, is_afspecwar_eod: bool
) -> None:
    profile = Profile(age=age, sex=sex, is_afspecwar_eod=is_afspecwar_eod)
    names = list(REAL.components)
    checked = 0
    for placements in [(p,) * len(names) for p in PLACEMENTS] + [
        ("below", "best", "best", "best"),
        ("middle", "minimum", "best", "middle"),
        ("best", "best", "below", "best"),
    ]:
        values = {
            REAL.components[name].events[0]: _result_at(
                REAL, profile, REAL.components[name].events[0], placement
            )
            for name, placement in zip(names, placements, strict=True)
        }
        results = Results(values=values)
        for target in TARGETS:
            plan = plan_to_target(REAL, profile, target, results)
            for option in plan.options:
                (change,) = option.changes
                new_values = {**values, change.event: change.to_result}
                report = calculate_score(REAL, profile, Results(values=new_values))
                assert report.total is not None
                assert report.total >= target
                assert report.total == option.projected_total
                assert report.missed_minimums == []
                checked += 1

                # Minimal: one bracket worse does not work (it misses the target or a minimum).
                table = find_table(
                    REAL,
                    change.event,
                    profile.sex,
                    profile.age,
                    is_afspecwar_eod=profile.is_afspecwar_eod,
                )
                index = [b.threshold for b in table.brackets].index(change.to_result)
                if index + 1 < len(table.brackets):
                    worse = {**values, change.event: table.brackets[index + 1].threshold}
                    worse_report = calculate_score(REAL, profile, Results(values=worse))
                    assert worse_report.total is not None
                    assert worse_report.total < target or worse_report.missed_minimums
    assert checked > 0
