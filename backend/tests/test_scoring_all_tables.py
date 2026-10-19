"""Properties checked on every table in the real standards file (144 tables).

These test the scoring code against the shape of the data. They do not prove the chart values are
right. The golden CSV files and the PDF spot checks do that. Each property is one test that loops
over all tables and lists every table that breaks it.
"""

from collections.abc import Callable
from pathlib import Path

from app.core.scoring import full_points_gap, minimum_gap, score_event
from app.core.standards import parse_standards
from app.models import EventTable

ROOT = Path(__file__).parents[1]
TABLES = parse_standards((ROOT / "data" / "standards" / "2026-03-01.json").read_bytes()).tables

# A property returns a message for each way one table breaks it, or an empty list.
Property = Callable[[EventTable], list[str]]


def _worse(table: EventTable, threshold: int) -> int:
    return threshold - 1 if table.higher_is_better else threshold + 1


def _better(table: EventTable, threshold: int) -> int:
    return threshold + 1 if table.higher_is_better else threshold - 1


def _violations(prop: Property) -> list[str]:
    return [
        f"{t.event} {t.sex} {t.age_min}-{t.age_max}: {message}"
        for t in TABLES
        for message in prop(t)
    ]


def test_every_table_is_covered() -> None:
    assert len(TABLES) == 144


def test_threshold_earns_its_row() -> None:
    def prop(table: EventTable) -> list[str]:
        expected_met = None if table.component_minimum is None else True
        return [
            f"result {b.threshold} gave {got}, expected {(b.points, expected_met)}"
            for b in table.brackets
            if (got := score_event(table, b.threshold)) != (b.points, expected_met)
        ]

    assert _violations(prop) == []


def test_one_worse_earns_the_next_row() -> None:
    def prop(table: EventTable) -> list[str]:
        return [
            f"result {_worse(table, upper.threshold)} gave {got}, expected {lower.points}"
            for upper, lower in zip(table.brackets, table.brackets[1:], strict=False)
            if (got := score_event(table, _worse(table, upper.threshold))[0]) != lower.points
        ]

    assert _violations(prop) == []


def test_worse_than_the_last_row_earns_zero() -> None:
    def prop(table: EventTable) -> list[str]:
        result = _worse(table, table.brackets[-1].threshold)
        # Events with a minimum fail it here. WHtR has no minimum, so it only earns 0.
        expected = (0.0, None if table.component_minimum is None else False)
        got = score_event(table, result)
        return [] if got == expected else [f"result {result} gave {got}, expected {expected}"]

    assert _violations(prop) == []


def test_minimum_gap_counts_from_the_minimum() -> None:
    def prop(table: EventTable) -> list[str]:
        minimum = table.component_minimum
        if minimum is None:
            got = minimum_gap(table, table.brackets[-1].threshold)
            return [] if got is None else [f"no minimum, but gap {got}"]
        cases = [(minimum, None), (_worse(table, minimum), 1), (_better(table, minimum), None)]
        return [
            f"result {result} gave gap {got}, expected {expected}"
            for result, expected in cases
            if (got := minimum_gap(table, result)) != expected
        ]

    assert _violations(prop) == []


def test_full_points_gap_matches_top_row_points() -> None:
    def prop(table: EventTable) -> list[str]:
        top = table.brackets[0]
        cases = [
            (top.threshold, None),
            (_better(table, top.threshold), None),
            (_worse(table, top.threshold), 1),
        ]
        problems = [
            f"result {result} gave gap {got}, expected {expected}"
            for result, expected in cases
            if (got := full_points_gap(table, result)) != expected
        ]
        # The gap is None exactly when the result earns the top row's points.
        for b in table.brackets:
            earns_top = score_event(table, b.threshold)[0] == top.points
            if earns_top != (full_points_gap(table, b.threshold) is None):
                problems.append(f"result {b.threshold}: points and gap disagree")
        return problems

    assert _violations(prop) == []


def test_better_than_the_top_row_earns_the_top_row() -> None:
    def prop(table: EventTable) -> list[str]:
        top = table.brackets[0]
        result = _better(table, top.threshold)
        got = score_event(table, result)[0]
        return [] if got == top.points else [f"result {result} gave {got}, expected {top.points}"]

    assert _violations(prop) == []


def test_better_results_never_earn_fewer_points() -> None:
    def prop(table: EventTable) -> list[str]:
        # Sweep every whole result from far below the last row to far above the top row.
        first, last = table.brackets[0].threshold, table.brackets[-1].threshold
        results = range(max(min(first, last) - 5, 0), max(first, last) + 6)
        ordered = results if table.higher_is_better else reversed(results)
        previous = -1.0
        for result in ordered:
            points = score_event(table, result)[0]
            if points < previous:
                return [f"result {result} earns {points}, fewer than a worse result ({previous})"]
            previous = points
        return []

    assert _violations(prop) == []
