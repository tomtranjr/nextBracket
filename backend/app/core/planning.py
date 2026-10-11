"""Plan how to reach a target total. Pure: no I/O, no LLM.

Every number comes from the standards file. The plan walks the chart brackets from worst to
best, so it needs no optimizer, and it scores each step with `score_event` from `scoring.py`.
"""

from app.core.scoring import events_by_component, score_event
from app.core.standards import find_table
from app.models import (
    EventChange,
    EventTable,
    PlanOption,
    PlanResult,
    PlanStatus,
    Profile,
    Results,
    StandardsFile,
)


def _baseline(table: EventTable, result: int | None) -> tuple[float, bool | None]:
    """Return (points, minimum_met) for the starting point of one event.

    With no result, the member starts at the component minimum. Body composition has no
    minimum, so it starts at 0 points.
    """
    if result is not None:
        return score_event(table, result)
    if table.component_minimum is None:
        return 0.0, None
    return score_event(table, table.component_minimum)


def plan_to_target(
    standards: StandardsFile,
    profile: Profile,
    target: float,
    current: Results | None = None,
) -> PlanResult:
    """Find the events that, improved alone, bring the member to `target` total points.

    The plan keeps each component's event: the one in `current`, or the first one the standards
    file lists. It never switches from run to shuttle. An option must reach the target and meet
    every component minimum. Raises `ValueError` for a negative target, an unknown event, or
    two events in one component.
    """
    if target < 0:
        raise ValueError(f"target must not be negative: {target}")
    current = current or Results()
    chosen = events_by_component(standards, current)

    # One row per component: (component, table, result or None, points, minimum_met).
    rows = []
    for name, component in standards.components.items():
        event = chosen.get(name, component.events[0])
        table = find_table(
            standards, event, profile.sex, profile.age, is_afspecwar_eod=profile.is_afspecwar_eod
        )
        result = current.values.get(event)
        points, minimum_met = _baseline(table, result)
        rows.append((name, table, result, points, minimum_met))

    current_total = sum(row[3] for row in rows)
    max_total = sum(row[1].brackets[0].points for row in rows)
    assumed = [name for name, _, result, _, _ in rows if result is None]
    any_missed = any(row[4] is False for row in rows)

    options: list[PlanOption] = []
    status: PlanStatus
    if current_total >= target and not any_missed:
        status = "already_met"
    elif target > max_total:
        status = "impossible"
    else:
        for index, (name, table, result, points, _) in enumerate(rows):
            others = rows[:index] + rows[index + 1 :]
            if any(other[4] is False for other in others):
                # Only this event could fix a missed minimum elsewhere, so it cannot do it.
                continue
            others_total = sum(other[3] for other in others)
            # Brackets are listed best first. Walk from the worst, so the first match is the
            # smallest improvement that works.
            for bracket in reversed(table.brackets):
                new_points, minimum_met = score_event(table, bracket.threshold)
                if minimum_met is False or others_total + new_points < target:
                    continue
                options.append(
                    PlanOption(
                        kind="single_event",
                        changes=[
                            EventChange(
                                component=name,
                                event=table.event,
                                unit=table.unit,
                                from_result=result,
                                to_result=bracket.threshold,
                                delta=None if result is None else bracket.threshold - result,
                                from_points=points,
                                to_points=new_points,
                            )
                        ],
                        projected_total=others_total + new_points,
                    )
                )
                break
        status = "options" if options else "no_single_event_option"

    return PlanResult(
        version=standards.version,
        effective_date=standards.effective_date,
        target=target,
        status=status,
        current_total=current_total,
        max_total=max_total,
        assumed_components=assumed,
        options=options,
    )
