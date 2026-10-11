"""Plan how to reach a target total. Pure: no I/O, no LLM.

Every number comes from the standards file. The plan walks the chart brackets from worst to
best, so it needs no optimizer, and it scores each step with `score_event` from `scoring.py`.
"""

from dataclasses import dataclass
from typing import Literal

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


@dataclass
class _Walker:
    """One component while a multi-event plan raises it, one bracket at a time."""

    component: str
    table: EventTable
    start_result: int | None
    start_points: float
    # Where the member stands, as a result value. None: no result and no minimum to start from,
    # so the member stands beyond the worst row.
    start_position: int | None
    position: int | None
    points: float
    minimum_met: bool | None


def _walker(
    name: str, table: EventTable, result: int | None, points: float, met: bool | None
) -> _Walker:
    position = result if result is not None else table.component_minimum
    return _Walker(name, table, result, points, position, position, points, met)


def _is_better(table: EventTable, threshold: int, position: int | None) -> bool:
    if position is None:
        return True
    return threshold > position if table.higher_is_better else threshold < position


def _next_step(walker: _Walker) -> tuple[int, float] | None:
    """Return (threshold, points) of the next bracket up, or None at the top of the chart."""
    below_minimum = walker.minimum_met is False
    # Brackets are listed best first. Walk from the worst, so the first match is the next step.
    for bracket in reversed(walker.table.brackets):
        if not _is_better(walker.table, bracket.threshold, walker.position):
            continue
        points, minimum_met = score_event(walker.table, bracket.threshold)
        if minimum_met is False:
            continue
        # A member below the minimum has 0 points, so the first bracket that meets it is a step.
        if below_minimum or points > walker.points:
            return bracket.threshold, points
    return None


def _move(walker: _Walker, step: tuple[int, float]) -> None:
    walker.position, walker.points = step
    # `_next_step` only returns brackets that meet the minimum.
    walker.minimum_met = None if walker.table.component_minimum is None else True


def _effort(walker: _Walker, threshold: int) -> float:
    """The share of the chart a step covers. Reps and seconds do not compare, so use the share."""
    worst = walker.table.brackets[-1].threshold
    span = max(1, abs(walker.table.brackets[0].threshold - worst))
    if walker.position is None:
        return (abs(threshold - worst) + 1) / span
    return abs(threshold - walker.position) / span


def _is_done(walkers: list[_Walker], target: float) -> bool:
    return sum(w.points for w in walkers) >= target and all(
        w.minimum_met is not False for w in walkers
    )


def _fix_minimums(walkers: list[_Walker]) -> bool:
    """Raise every event below its minimum to the first bracket that meets it."""
    for walker in walkers:
        if walker.minimum_met is False:
            step = _next_step(walker)
            if step is None:
                return False
            _move(walker, step)
    return True


def _quick_wins(walkers: list[_Walker], target: float) -> bool:
    """Take the step with the most points for the least effort, until the target is met."""
    if not _fix_minimums(walkers):
        return False
    while not _is_done(walkers, target):
        best: tuple[float, _Walker, tuple[int, float]] | None = None
        for walker in walkers:
            step = _next_step(walker)
            if step is None:
                continue
            value = (step[1] - walker.points) / _effort(walker, step[0])
            # A tie keeps the earlier component, so the result does not depend on dict order.
            if best is None or value > best[0]:
                best = (value, walker, step)
        if best is None:
            return False
        _move(best[1], best[2])
    return True


def _balanced(walkers: list[_Walker], target: float) -> bool:
    """Raise each event one bracket in turn, until the target is met."""
    if not _fix_minimums(walkers):
        return False
    while not _is_done(walkers, target):
        progressed = False
        for walker in walkers:
            step = _next_step(walker)
            if step is not None and not _is_done(walkers, target):
                _move(walker, step)
                progressed = True
        if not progressed:
            return False
    return True


def _walk_option(
    kind: Literal["quick_wins", "balanced"],
    walkers: list[_Walker],
    target: float,
) -> PlanOption | None:
    """Run one strategy and report only the events that changed."""
    reached = _quick_wins(walkers, target) if kind == "quick_wins" else _balanced(walkers, target)
    if not reached:
        return None
    changes = [
        EventChange(
            component=w.component,
            event=w.table.event,
            unit=w.table.unit,
            from_result=w.start_result,
            to_result=w.position,
            delta=None if w.start_result is None else w.position - w.start_result,
            from_points=w.start_points,
            to_points=w.points,
        )
        for w in walkers
        if w.position is not None and w.position != w.start_position
    ]
    return PlanOption(kind=kind, changes=changes, projected_total=sum(w.points for w in walkers))


def plan_to_target(
    standards: StandardsFile,
    profile: Profile,
    target: float,
    current: Results | None = None,
) -> PlanResult:
    """Find ways to bring the member to `target` total points.

    Options, in order: one event alone (at most one per component), then `quick_wins` (the most
    points for the least effort first), then `balanced` (one bracket per event in turn). An
    option that repeats an earlier one is left out. The plan keeps each component's event: the
    one in `current`, or the first one the standards file lists. It never switches from run to
    shuttle. An option must reach the target and meet every component minimum. Raises
    `ValueError` for a negative target, an unknown event, or two events in one component.
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
        # Multi-event options. One that repeats an earlier option (one event only) adds nothing.
        for kind in ("quick_wins", "balanced"):
            walkers = [
                _walker(name, table, result, points, met)
                for name, table, result, points, met in rows
            ]
            option = _walk_option(kind, walkers, target)
            if option is not None and all(option.changes != o.changes for o in options):
                options.append(option)
        status = "options"

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
