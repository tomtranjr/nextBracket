"""Every missed component minimum scores 0 and a complete test is Unsatisfactory.

Runs `score_event` and `calculate_score` on the standards JSON in this repo.
Exit 0 when the property holds. Exit 1 and print one counterexample when it does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "backend"))

from app.core.scoring import calculate_score, categorize, score_event  # noqa: E402
from app.core.standards import find_table, parse_standards  # noqa: E402
from app.models import EventTable, Profile, Results, Sex, StandardsFile  # noqa: E402

STANDARDS_DIR = REPO / "backend" / "data" / "standards"
# A member outside the male under-25 band, so AFSPECWAR lookup is not an accident of age.
AFSPECWAR_AGE = 40
AFSPECWAR_SEX: Sex = "F"


class Counterexample(Exception):
    """The product code broke the property. The message is the counterexample."""


def ages_in_band(table: EventTable) -> list[int]:
    """Ages a Profile can hold that still fall in this table's band."""
    if table.age_max is not None and table.age_max < 17:
        return []
    low = max(table.age_min, 17)
    high = 70 if table.age_max is None else min(table.age_max, 70)
    if low > high or low > 70:
        return []
    if low == high:
        return [low]
    return [low, high]


def result_hi(table: EventTable) -> int:
    """Last integer to feed `score_event`: one step past a miss, and the top row."""
    top = table.brackets[0].threshold
    minimum = table.component_minimum
    if minimum is None:
        return top
    # Includes the top row and one result past the minimum, for either direction.
    return max(top, minimum) + 1


def step_past(table: EventTable) -> int | None:
    """One result worse than the minimum, or None when that result would be negative."""
    minimum = table.component_minimum
    if minimum is None:
        return None
    if table.higher_is_better:
        worse = minimum - 1
        return None if worse < 0 else worse
    return minimum + 1


def meets(table: EventTable, result: int) -> bool:
    minimum = table.component_minimum
    if minimum is None:
        return True
    return result >= minimum if table.higher_is_better else result <= minimum


def minimum_row_points(table: EventTable) -> float:
    minimum = table.component_minimum
    if minimum is None:
        raise Counterexample(f"{table.event} has no minimum row to read")
    for bracket in table.brackets:
        if bracket.threshold == minimum:
            return bracket.points
    raise Counterexample(
        f"{table.event} {table.sex} ages {table.age_min}-{table.age_max}: "
        f"minimum {minimum} is not a bracket threshold"
    )


def check_score_event(table: EventTable) -> int:
    checked = 0
    for result in range(0, result_hi(table) + 1):
        points, minimum_met = score_event(table, result)
        where = f"{table.event} {table.sex} ages {table.age_min}-{table.age_max} result {result}"
        if not meets(table, result):
            if points != 0.0 or minimum_met is not False:
                raise Counterexample(
                    f"{where}: missed the minimum and scored {points} "
                    f"(minimum_met={minimum_met}), expected 0 points and minimum_met False"
                )
        else:
            if minimum_met is not True:
                raise Counterexample(f"{where}: met the minimum but minimum_met={minimum_met}")
            if result == table.component_minimum and points != minimum_row_points(table):
                raise Counterexample(
                    f"{where}: exactly at the minimum scored {points}, "
                    f"expected the chart row {minimum_row_points(table)}"
                )
        checked += 1
    return checked


def other_components_at_top(
    standards: StandardsFile,
    profile: Profile,
    failing_event: str,
    failing_result: int,
) -> Results:
    values: dict[str, int] = {}
    for component in standards.components.values():
        event = failing_event if failing_event in component.events else component.events[0]
        if event == failing_event:
            values[event] = failing_result
            continue
        table = find_table(
            standards,
            event,
            profile.sex,
            profile.age,
            is_afspecwar_eod=profile.is_afspecwar_eod,
        )
        values[event] = table.brackets[0].threshold
    return Results(values=values)


def check_complete(
    standards: StandardsFile,
    table: EventTable,
    age: int,
    *,
    afspecwar: bool,
) -> None:
    if afspecwar:
        profile = Profile(age=AFSPECWAR_AGE, sex=AFSPECWAR_SEX, is_afspecwar_eod=True)
        table = find_table(standards, table.event, profile.sex, profile.age, is_afspecwar_eod=True)
    else:
        profile = Profile(age=age, sex=table.sex, is_afspecwar_eod=False)
    worse = step_past(table)
    if worse is None:
        return
    results = other_components_at_top(standards, profile, table.event, worse)
    report = calculate_score(standards, profile, results)
    scored = next((row for row in report.components if row.event == table.event), None)
    where = (
        f"version {standards.version} age {profile.age} sex {profile.sex} "
        f"afspecwar {profile.is_afspecwar_eod} {table.event}={worse} "
        f"with other components at their top row {results.values}"
    )
    if scored is None or report.total is None or report.not_scored:
        raise Counterexample(f"checker built an illegal result ({where}): {report}")
    if scored.points != 0.0 or scored.minimum_met is not False or scored.minimum_gap != 1:
        raise Counterexample(
            f"{where}: component points {scored.points}, minimum_met {scored.minimum_met}, "
            f"gap {scored.minimum_gap}; expected 0 points, missed, gap 1"
        )
    if table.event not in report.missed_minimums or report.category != "unsatisfactory":
        raise Counterexample(
            f"{where}: category {report.category}, missed {report.missed_minimums}, "
            f"total {report.total}; expected unsatisfactory because the minimum was missed"
        )


def check_categorize(standards: StandardsFile) -> None:
    passing = standards.passing_total
    # A total that would otherwise be Excellent must still fail when a minimum is missed.
    if categorize(90.0, passing, True) != "unsatisfactory":
        raise Counterexample(
            f"version {standards.version}: categorize(90, missed minimum) was not unsatisfactory"
        )
    if categorize(float(passing), passing, True) != "unsatisfactory":
        raise Counterexample(
            f"version {standards.version}: categorize({passing}, missed minimum) "
            "was not unsatisfactory"
        )


def check_file(path: Path) -> tuple[int, int]:
    standards = parse_standards(path.read_bytes())
    check_categorize(standards)
    event_results = 0
    complete = 0
    for table in standards.tables:
        if table.component_minimum is None:
            continue
        event_results += check_score_event(table)
        for age in ages_in_band(table):
            looked_up = find_table(standards, table.event, table.sex, age)
            if looked_up is not table:
                raise Counterexample(
                    f"{table.event} {table.sex} age {age} resolved to a different table "
                    f"than ages {table.age_min}-{table.age_max}"
                )
            check_complete(standards, table, age, afspecwar=False)
            complete += 1
    for event in standards.afspecwar_eod.events:
        anchor = find_table(
            standards,
            event,
            standards.afspecwar_eod.sex,
            max(standards.afspecwar_eod.age_min, 17),
        )
        check_complete(standards, anchor, AFSPECWAR_AGE, afspecwar=True)
        complete += 1
    return event_results, complete


def main() -> None:
    files = sorted(STANDARDS_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"no standards files in {STANDARDS_DIR}")
    for path in files:
        event_results, complete = check_file(path)
        if event_results == 0 or complete == 0:
            raise SystemExit(f"{path.name}: checked nothing")
        print(
            f"passed {path.name}: {event_results} score_event results, {complete} complete scores"
        )


if __name__ == "__main__":
    try:
        main()
    except Counterexample as exc:
        print(f"failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
