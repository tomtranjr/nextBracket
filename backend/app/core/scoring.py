"""Score a member's results against one version of the standards. Pure: no I/O, no LLM.

Every number comes from the standards file. The only constant here is the Excellent cutoff.
"""

from app.core.standards import find_table
from app.models import (
    Bracket,
    Category,
    ComponentScore,
    EventTable,
    Profile,
    Results,
    ScoreReport,
    StandardsFile,
)

# DAFMAN 36-2905 Table 3.3. The passing total (75) is in the standards file. This is not.
EXCELLENT_TOTAL = 90.0


def _meets(table: EventTable, result: int, threshold: int) -> bool:
    return result >= threshold if table.higher_is_better else result <= threshold


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


def categorize(total: float, passing_total: int, minimums_missed: bool) -> Category:
    if minimums_missed or total < passing_total:
        return "unsatisfactory"
    return "excellent" if total >= EXCELLENT_TOTAL else "satisfactory"


def calculate_score(standards: StandardsFile, profile: Profile, results: Results) -> ScoreReport:
    """Score `results` for `profile`.

    A member takes one event per component. If a component has no result, the report lists it in
    `not_scored` and gives no total, because the regulation has no formula for a partial set
    (design doc 16.2). Raises `ValueError` for an unknown event or two events in one component.
    """
    event_to_component = {
        event: name for name, comp in standards.components.items() for event in comp.events
    }
    by_component: dict[str, str] = {}
    for event in results.values:
        name = event_to_component.get(event)
        if name is None:
            raise ValueError(f"unknown event: {event!r}")
        if name in by_component:
            raise ValueError(f"two events for {name!r}: {by_component[name]!r} and {event!r}")
        by_component[name] = event

    scores: list[ComponentScore] = []
    not_scored: list[str] = []
    for name, component in standards.components.items():
        chosen = by_component.get(name)
        if chosen is None:
            not_scored.append(name)
            continue
        table = find_table(
            standards, chosen, profile.sex, profile.age, is_afspecwar_eod=profile.is_afspecwar_eod
        )
        result = results.values[chosen]
        points, minimum_met = score_event(table, result)
        scores.append(
            ComponentScore(
                component=name,
                event=chosen,
                result=result,
                points=points,
                max_points=component.max_points,
                minimum_met=minimum_met,
            )
        )

    missed = [s.event for s in scores if s.minimum_met is False]
    total: float | None = None
    category: Category | None = None
    if not not_scored:
        total = sum(s.points for s in scores)
        category = categorize(total, standards.passing_total, bool(missed))
    return ScoreReport(
        version=standards.version,
        effective_date=standards.effective_date,
        components=scores,
        not_scored=not_scored,
        total=total,
        category=category,
        missed_minimums=missed,
    )
