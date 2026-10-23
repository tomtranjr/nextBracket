"""Golden cases: expected points read from the printed charts, not from the JSON.

See tests/golden/README.md for how the CSV files were made. Each file is one test. It checks
every row and lists all the rows that differ, so one bad chart value shows up as one failure
with a full report.
"""

import csv
from pathlib import Path

import pytest

from app.core.scoring import score_event, score_walk
from app.core.standards import find_table, parse_standards
from app.models import Profile, Sex, StandardsFile

ROOT = Path(__file__).parents[1]
GOLDEN = Path(__file__).parent / "golden"

Case = tuple[Sex, int, str, int, float, bool | None]


def _load(name: str) -> list[Case]:
    rows: list[Case] = []
    with (GOLDEN / name).open(newline="") as f:
        for row in csv.DictReader(f):
            sex: Sex = "M" if row["sex"] == "M" else "F"
            met = {"true": True, "false": False, "": None}[row["minimum_met"]]
            rows.append(
                (sex, int(row["age"]), row["event"], int(row["result"]), float(row["points"]), met)
            )
    return rows


@pytest.fixture(scope="module")
def standards() -> StandardsFile:
    return parse_standards((ROOT / "data" / "standards" / "2026-03-01.json").read_bytes())


def _differences(
    standards: StandardsFile, cases: list[Case], *, is_afspecwar_eod: bool = False
) -> list[str]:
    found: list[str] = []
    for sex, age, event, result, points, minimum_met in cases:
        table = find_table(standards, event, sex, age, is_afspecwar_eod=is_afspecwar_eod)
        got = score_event(table, result)
        if got != (points, minimum_met):
            found.append(
                f"{event} {sex} age {age} result {result}: "
                f"expected {(points, minimum_met)}, got {got}"
            )
    return found


def test_chart_cases(standards: StandardsFile) -> None:
    cases = _load("chart_cases.csv")
    assert len(cases) > 800  # a guard so an empty or cut file cannot pass
    assert _differences(standards, cases) == []


def test_age_edges(standards: StandardsFile) -> None:
    cases = _load("age_edges.csv")
    assert len(cases) >= 9
    assert _differences(standards, cases) == []


def test_afspecwar_eod_cases(standards: StandardsFile) -> None:
    cases = _load("afspecwar_eod_cases.csv")
    assert len(cases) > 300
    assert _differences(standards, cases, is_afspecwar_eod=True) == []


def test_push_up_male_30_34_follows_the_printed_table(standards: StandardsFile) -> None:
    # The chart prints 26 for both 3.0 and 2.5 points. 26 earns 3.0. 25 misses the minimum.
    table = find_table(standards, "push_up", "M", 32)
    assert score_event(table, 26) == (3.0, True)
    assert score_event(table, 25) == (0.0, False)


def test_run_39_points_uses_the_main_table(standards: StandardsFile) -> None:
    # The AFSPECWAR/EOD page prints 17:16 here and the main male under-25 table prints 17:13.
    # We use the main table (decision recorded in the build plan).
    table = find_table(standards, "run_2mile", "M", 22)
    assert score_event(table, 1033) == (39.0, True)
    assert score_event(table, 1034) == (38.5, True)


def test_walk_cases(standards: StandardsFile) -> None:
    found: list[str] = []
    count = 0
    with (GOLDEN / "walk_cases.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            count += 1
            sex: Sex = "M" if row["sex"] == "M" else "F"
            profile = Profile(
                age=int(row["age"]), sex=sex, is_afspecwar_eod=row["is_afspecwar_eod"] == "true"
            )
            got = score_walk(standards, profile, int(row["result"])).passed
            if got != (row["passed"] == "true"):
                found.append(f"walk {row}: got passed={got}")
    assert count >= 30
    assert found == []
