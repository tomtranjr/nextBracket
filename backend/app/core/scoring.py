"""Score a member's results against one version of the standards. Pure: no I/O, no LLM.

Every number comes from the standards file. The only constant here is the Excellent cutoff.
"""

from app.core.standards import find_table, find_walk_standard
from app.models import (
    WALK_COMPONENT,
    WALK_EVENT,
    Bracket,
    Category,
    ComponentScore,
    EventTable,
    Profile,
    Results,
    ScoreReport,
    StandardsFile,
    WalkScore,
)

# DAFMAN 36-2905 Table 3.3. The passing total (75) is in the standards file. This is not.
EXCELLENT_TOTAL = 90.0

# DAFMAN 36-2905 para 3.7.3 scores a walker "in the same way ... as if the member were exempt from
# the cardiorespiratory component" (para 3.6.2), but gives no formula. We use this one.
WALK_ASSUMPTION = (
    "Walk composite = points earned / points possible without cardio x 100. "
    "DAFMAN 36-2905 paras 3.7.3 and 3.6.2 score a walker as if exempt from cardio "
    "but do not state the formula."
)


def _meets(table: EventTable, result: int, threshold: int) -> bool:
    return result >= threshold if table.higher_is_better else result <= threshold


def check_result(event: str, result: int, *, higher_is_better: bool) -> None:
    """Raise `ValueError` for a lower-is-better result of 0 or less.

    A 0:00 run or walk, or a WHtR of 0.00, is a typo, not a top score. A 0 for reps, shuttles,
    or a plank is a real result, so higher-is-better events accept it.
    """
    if not higher_is_better and result <= 0:
        raise ValueError(f"{event}: result must be above 0: {result}")


def find_bracket(table: EventTable, result: int) -> Bracket | None:
    """Return the best bracket the result meets, or None if it is worse than every row."""
    # Brackets are listed best first, so the first one met is the best one met.
    for bracket in table.brackets:
        if _meets(table, result, bracket.threshold):
            return bracket
    return None


def score_event(table: EventTable, result: int) -> tuple[float, bool | None]:
    """Return (points, minimum_met) for one event. `minimum_met` is None if there is no minimum."""
    minimum = table.component_minimum
    minimum_met = None if minimum is None else _meets(table, result, minimum)
    if minimum_met is False:
        # Below the minimum earns 0 points and fails the component (para 3.7.4).
        return 0.0, False
    bracket = find_bracket(table, result)
    return (0.0 if bracket is None else bracket.points), minimum_met


def minimum_gap(table: EventTable, result: int) -> int | None:
    """Return how far `result` is from the component minimum, or None if it meets it or has none."""
    minimum = table.component_minimum
    if minimum is None or _meets(table, result, minimum):
        return None
    # A distance, so the caller needs no direction: run seconds over, or reps under.
    return abs(result - minimum)


def full_points_gap(table: EventTable, result: int) -> int | None:
    """Return how far `result` is from the top row, or None if it already earns full points."""
    top = table.brackets[0].threshold
    return None if _meets(table, result, top) else abs(result - top)


def categorize(total: float, passing_total: int, minimums_missed: bool) -> Category:
    if minimums_missed or total < passing_total:
        return "unsatisfactory"
    return "excellent" if total >= EXCELLENT_TOTAL else "satisfactory"


def events_by_component(standards: StandardsFile, results: Results) -> dict[str, str]:
    """Map each component to the event the member took. Raises `ValueError` on bad input.

    Bad input is an unknown event, or two events for one component.
    """
    event_to_component = {
        event: name for name, comp in standards.components.items() for event in comp.events
    }
    # The walk fills the cardio slot, so walk plus run is "two events for cardio".
    if WALK_COMPONENT in standards.components:
        event_to_component[WALK_EVENT] = WALK_COMPONENT
    by_component: dict[str, str] = {}
    for event in results.values:
        name = event_to_component.get(event)
        if name is None:
            raise ValueError(f"unknown event: {event!r}")
        if name in by_component:
            raise ValueError(f"two events for {name!r}: {by_component[name]!r} and {event!r}")
        by_component[name] = event
    return by_component


def score_walk(standards: StandardsFile, profile: Profile, result: int) -> WalkScore:
    """Pass/fail the 2 km walk. A time at or under the maximum passes (Table 3.1)."""
    # The walk is a time, so lower is better.
    check_result(WALK_EVENT, result, higher_is_better=False)
    max_time = find_walk_standard(standards, profile.sex, profile.age).max_time
    passed = result <= max_time
    return WalkScore(
        result=result, max_time=max_time, passed=passed, gap=None if passed else result - max_time
    )


def calculate_score(standards: StandardsFile, profile: Profile, results: Results) -> ScoreReport:
    """Score `results` for `profile`.

    A member takes one event per component. If a component has no result, the report lists it in
    `not_scored` and gives no total, because the regulation has no formula for a partial set
    (design doc 16.2). Raises `ValueError` for an unknown event, two events in one component,
    or a run, walk, or WHtR result of 0 or less (see `check_result`).

    The 2 km walk fills the cardio slot with a pass/fail and no points. A walker's total is
    scaled to 100 from the other components (see `WALK_ASSUMPTION`). A walk fail is
    Unsatisfactory, and a walk pass cannot be Excellent (paras 3.7.3, 3.10.1).
    """
    by_component = events_by_component(standards, results)

    scores: list[ComponentScore] = []
    not_scored: list[str] = []
    walk: WalkScore | None = None
    points_possible = 0
    for name, component in standards.components.items():
        chosen = by_component.get(name)
        if chosen is None:
            not_scored.append(name)
            points_possible += component.max_points
            continue
        if chosen == WALK_EVENT:
            walk = score_walk(standards, profile, results.values[chosen])
            continue
        points_possible += component.max_points
        table = find_table(
            standards, chosen, profile.sex, profile.age, is_afspecwar_eod=profile.is_afspecwar_eod
        )
        result = results.values[chosen]
        check_result(chosen, result, higher_is_better=table.higher_is_better)
        points, minimum_met = score_event(table, result)
        scores.append(
            ComponentScore(
                component=name,
                event=chosen,
                result=result,
                points=points,
                max_points=component.max_points,
                minimum_met=minimum_met,
                minimum=table.component_minimum,
                minimum_gap=minimum_gap(table, result),
                full_points_at=table.brackets[0].threshold,
                full_points_gap=full_points_gap(table, result),
            )
        )

    missed = [s.event for s in scores if s.minimum_met is False]
    total: float | None = None
    earned = 0.0
    category: Category | None = None
    if not not_scored:
        earned = sum(s.points for s in scores)
        # Multiply first: 27.5 / 50 * 100 is 55.00000000000001, but 27.5 * 100 / 50 is 55.0.
        total = earned if walk is None else earned * 100 / points_possible
        category = categorize(total, standards.passing_total, bool(missed))
        if walk is not None and not walk.passed:
            category = "unsatisfactory"
        elif walk is not None and category == "excellent":
            category = "satisfactory"
    return ScoreReport(
        version=standards.version,
        effective_date=standards.effective_date,
        components=scores,
        not_scored=not_scored,
        total=total,
        points_earned=None if total is None else earned,
        category=category,
        missed_minimums=missed,
        points_possible=points_possible,
        walk=walk,
        assumptions=[] if walk is None else [WALK_ASSUMPTION],
    )
