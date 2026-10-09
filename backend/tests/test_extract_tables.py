"""Tests for `scripts/extract_tables.py` and the committed standards JSON.

The spot-check numbers below were read by hand from `PFRA Scoring Charts.pdf`, not produced by the
extractor, so they check the extractor instead of repeating it.
"""

from typing import Any

import pdfplumber
import pytest

from app.core.standards import parse_standards
from app.models import EventTable, StandardsFile
from scripts import extract_tables
from scripts.extract_tables import (
    AFSPECWAR_COLUMNS,
    AFSPECWAR_PAGE_INDEX,
    DEFAULT_OUT,
    DEFAULT_PDF,
    PAGES,
    AfspecwarColumn,
    check_afspecwar_matches,
    extract_afspecwar_columns,
    extract_event_tables,
    extract_standards,
    parse_age_band,
    parse_cell,
    parse_ratio,
    parse_time,
    render_json,
)


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("3:40", 220), (":55", 55), ("13:25", 805), ("29:40", 1780), ("0:05", 5)],
)
def test_parse_time(text: str, seconds: int) -> None:
    assert parse_time(text) == seconds


@pytest.mark.parametrize("text", ["3:4", "340", "3:40:00", "", "a:bc"])
def test_parse_time_rejects_bad_input(text: str) -> None:
    with pytest.raises(ValueError, match="mm:ss"):
        parse_time(text)


def test_parse_ratio_uses_hundredths() -> None:
    assert parse_ratio("0.49") == 49
    assert parse_ratio("0.60") == 60


@pytest.mark.parametrize("text", ["0.5", "0.499", "49", ".49"])
def test_parse_ratio_rejects_bad_input(text: str) -> None:
    with pytest.raises(ValueError, match="ratio"):
        parse_ratio(text)


@pytest.mark.parametrize(
    ("raw", "unit", "threshold", "is_minimum", "comparator"),
    [
        ("≥ 67", "reps", 67, False, "≥"),
        ("66", "reps", 66, False, None),
        ("30*", "reps", 30, True, None),
        ("≤ 13:25", "seconds", 805, False, "≤"),
        ("19:45*", "seconds", 1185, True, None),
        (":55*", "seconds", 55, True, None),
        ("≤ 0.49", "hundredths", 49, False, "≤"),
        ("≥ 0.60", "hundredths", 60, False, "≥"),
    ],
)
def test_parse_cell(
    raw: str, unit: str, threshold: int, is_minimum: bool, comparator: str | None
) -> None:
    cell = parse_cell(raw, unit)
    assert (cell.threshold, cell.is_minimum, cell.comparator) == (
        threshold,
        is_minimum,
        comparator,
    )


@pytest.mark.parametrize("raw", [None, "", "abc", "1.5", "12 13"])
def test_parse_cell_rejects_bad_input(raw: str | None) -> None:
    with pytest.raises(ValueError):
        parse_cell(raw, "reps")


def test_parse_age_band() -> None:
    assert parse_age_band("Under 25") == (0, 24)
    assert parse_age_band("25-29") == (25, 29)
    assert parse_age_band("60 and Over") == (60, None)
    with pytest.raises(ValueError, match="age band"):
        parse_age_band("teens")


def test_extract_event_tables_rejects_wrong_column_count() -> None:
    with pytest.raises(ValueError, match="columns"):
        extract_event_tables([["a", "b"]] * 5, PAGES[1])


@pytest.fixture(scope="module")
def committed() -> StandardsFile:
    return parse_standards(DEFAULT_OUT.read_text(encoding="utf-8"))


def _table(standards: StandardsFile, event: str, sex: str, age_min: int) -> EventTable:
    (match,) = (
        t for t in standards.tables if t.event == event and t.sex == sex and t.age_min == age_min
    )
    return match


def test_committed_json_matches_a_fresh_extraction() -> None:
    """If this fails, either the PDF or the script changed without regenerating the JSON."""
    fresh = render_json(extract_standards(DEFAULT_PDF))
    assert DEFAULT_OUT.read_text(encoding="utf-8") == fresh


def test_committed_json_has_every_event_sex_and_band(committed: StandardsFile) -> None:
    assert len(committed.tables) == len(PAGES) * 2 * 9


# (event, sex, age_min, top threshold, top points, minimum threshold, lowest listed points)
SPOT_CHECKS = [
    ("whtr", "M", 0, 49, 20.0, None, 0.0),
    ("whtr", "F", 60, 49, 20.0, None, 0.0),
    ("push_up", "M", 0, 67, 15.0, 30, 2.5),
    ("push_up", "F", 60, 28, 15.0, 3, 2.5),
    ("hand_release_push_up", "M", 0, 52, 15.0, 27, 2.5),
    ("sit_up", "M", 0, 58, 15.0, 33, 2.5),
    ("cross_leg_reverse_crunch", "F", 25, 56, 15.0, 31, 2.5),
    ("forearm_plank", "M", 0, 220, 15.0, 95, 2.5),
    ("forearm_plank", "F", 60, 175, 15.0, 50, 2.5),
    ("run_2mile", "M", 0, 805, 50.0, 1185, 35.0),
    ("run_2mile", "F", 60, 1100, 50.0, 1780, 35.0),
    ("hamr_20m", "M", 0, 87, 50.0, 42, 35.0),
    ("hamr_20m", "F", 60, 50, 50.0, 11, 35.0),
]


@pytest.mark.parametrize(
    ("event", "sex", "age_min", "top", "top_points", "minimum", "low_points"), SPOT_CHECKS
)
def test_spot_checks_against_the_pdf(
    committed: StandardsFile,
    event: str,
    sex: str,
    age_min: int,
    top: int,
    top_points: float,
    minimum: int | None,
    low_points: float,
) -> None:
    table = _table(committed, event, sex, age_min)
    assert (table.brackets[0].threshold, table.brackets[0].points) == (top, top_points)
    assert table.component_minimum == minimum
    assert table.brackets[-1].points == low_points


def test_whtr_bracket_shape(committed: StandardsFile) -> None:
    # 11 printed rows: 20, 19, 18, 17, 16, 15, 12.5, 10, 7.5, 5, 2.5, then 0 for 0.60 and over.
    table = _table(committed, "whtr", "M", 0)
    assert [b.points for b in table.brackets] == [
        20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 12.5, 10.0, 7.5, 5.0, 2.5, 0.0,
    ]  # fmt: skip
    assert [b.threshold for b in table.brackets] == list(range(49, 60)) + [60]


def test_run_has_uneven_point_steps(committed: StandardsFile) -> None:
    # Printed rows: 50, 49.5, 49, then whole points 48 to 39, then 0.5 steps 38.5 to 35.
    # Do not assume a regular grid anywhere.
    points = [b.points for b in _table(committed, "run_2mile", "M", 0).brackets]
    assert points[:3] == [50.0, 49.5, 49.0]
    assert points[3] == 48.0
    assert len(points) == 21


def test_push_up_tie_override_keeps_printed_minimum(committed: StandardsFile) -> None:
    # The PDF prints 26 for both 3.0 and 2.5 points (M, 30-34). We keep the 3.0 row and the
    # printed minimum. See KNOWN_TIES in the script.
    table = _table(committed, "push_up", "M", 30)
    assert table.component_minimum == 26
    assert (table.brackets[-1].threshold, table.brackets[-1].points) == (26, 3.0)


@pytest.mark.xfail(
    strict=True,
    reason="Source PDF prints 26 for both 3.0 and 2.5 points (push-up M 30-34). "
    "Remove this test once the correct 2.5 row is confirmed and added.",
)
def test_push_up_m_30_34_has_a_2_5_point_row(committed: StandardsFile) -> None:
    assert _table(committed, "push_up", "M", 30).brackets[-1].points == 2.5


def test_committed_json_maps_afspecwar_eod_to_male_under_25(committed: StandardsFile) -> None:
    mapping = committed.afspecwar_eod
    assert (mapping.sex, mapping.age_min) == ("M", 0)
    assert mapping.events == list(AFSPECWAR_COLUMNS)
    assert "whtr" not in mapping.events  # WHtR is not on the AFSPECWAR/EOD chart


def test_afspecwar_page_columns_read_from_the_pdf() -> None:
    with pdfplumber.open(DEFAULT_PDF) as pdf:
        (rows,) = pdf.pages[AFSPECWAR_PAGE_INDEX].extract_tables()
    columns = extract_afspecwar_columns(rows)
    assert set(columns) == set(AFSPECWAR_COLUMNS)
    run = columns["run_2mile"]
    assert (run.brackets[0], run.brackets[-1], run.minimum) == ((805, 50.0), (1185, 35.0), 1185)
    assert (39.0, 1036) in [(points, threshold) for threshold, points in run.brackets]
    assert columns["push_up"].minimum == 30
    assert len(columns["push_up"].brackets) == 26


def _main_table() -> list[dict[str, Any]]:
    brackets = [(30, 15.0), (20, 10.0), (10, 5.0)]
    return [
        {
            "event": "push_up",
            "sex": "M",
            "age_min": 0,
            "component_minimum": 10,
            "brackets": [{"threshold": t, "points": p} for t, p in brackets],
        }
    ]


def _afspecwar(
    brackets: list[tuple[int, float]] | None = None, minimum: int | None = 10
) -> dict[str, AfspecwarColumn]:
    return {"push_up": AfspecwarColumn(brackets or [(30, 15.0), (20, 10.0), (10, 5.0)], minimum)}


@pytest.fixture
def no_known_diffs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract_tables, "KNOWN_AFSPECWAR_DIFFS", {})


def test_afspecwar_check_passes_when_columns_match(no_known_diffs: None) -> None:
    check_afspecwar_matches(_afspecwar(), _main_table())


def test_afspecwar_check_rejects_an_unexpected_difference(no_known_diffs: None) -> None:
    with pytest.raises(ValueError, match="AFSPECWAR/EOD has 21"):
        check_afspecwar_matches(_afspecwar([(30, 15.0), (21, 10.0), (10, 5.0)]), _main_table())


def test_afspecwar_check_rejects_a_different_minimum(no_known_diffs: None) -> None:
    with pytest.raises(ValueError, match="minimum"):
        check_afspecwar_matches(_afspecwar(minimum=20), _main_table())


def test_afspecwar_check_rejects_a_different_row_count(no_known_diffs: None) -> None:
    with pytest.raises(ValueError, match="rows"):
        check_afspecwar_matches(_afspecwar([(30, 15.0), (20, 10.0)]), _main_table())


def test_afspecwar_check_allows_a_listed_difference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract_tables, "KNOWN_AFSPECWAR_DIFFS", {("push_up", 5.0): (9, 10)})
    check_afspecwar_matches(
        _afspecwar([(30, 15.0), (20, 10.0), (9, 5.0)], minimum=10), _main_table()
    )


def test_afspecwar_check_rejects_a_stale_listed_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract_tables, "KNOWN_AFSPECWAR_DIFFS", {("push_up", 5.0): (9, 10)})
    with pytest.raises(ValueError, match="no longer match"):
        check_afspecwar_matches(_afspecwar(), _main_table())


@pytest.mark.xfail(
    strict=True,
    reason="The AFSPECWAR/EOD chart prints 17:16 (1036 s) for the 2 mile run at 39.0 points. The "
    "main male under-25 table prints 17:13 (1033 s) and is used. Remove this test once the "
    "correct value is confirmed.",
)
def test_run_39_points_agrees_across_both_charts(committed: StandardsFile) -> None:
    run = _table(committed, "run_2mile", "M", 0)
    assert next(b.threshold for b in run.brackets if b.points == 39.0) == 1036
