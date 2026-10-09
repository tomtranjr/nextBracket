import json
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.standards import parse_standards

Edit = Callable[[dict[str, Any]], None]


def _parse(data: dict[str, Any]) -> None:
    parse_standards(json.dumps(data))


def _find(data: dict[str, Any], event: str, sex: str, age_min: int) -> dict[str, Any]:
    for table in data["tables"]:
        if table["event"] == event and table["sex"] == sex and table["age_min"] == age_min:
            return table  # type: ignore[no-any-return]
    raise AssertionError("table not in fixture")


def test_valid_file_parses(standards_dict: dict[str, Any]) -> None:
    standards = parse_standards(json.dumps(standards_dict))
    assert standards.version == "test"
    assert standards.effective_date == date(2026, 3, 1)
    assert len(standards.tables) == 8


def test_accepts_bytes(standards_dict: dict[str, Any]) -> None:
    assert parse_standards(json.dumps(standards_dict).encode()).passing_total == 75


def test_rejects_malformed_json() -> None:
    with pytest.raises(ValidationError):
        parse_standards("{not json")


def test_rejects_string_numbers(standards_dict: dict[str, Any]) -> None:
    _find(standards_dict, "pushups", "M", 0)["brackets"][0]["threshold"] = "30"
    with pytest.raises(ValidationError):
        _parse(standards_dict)


def test_rejects_unknown_key(standards_dict: dict[str, Any]) -> None:
    standards_dict["pasing_total"] = 75
    with pytest.raises(ValidationError):
        _parse(standards_dict)


def _drop_table(data: dict[str, Any]) -> None:
    data["tables"].remove(_find(data, "whtr", "F", 30))


def _gap_in_ages(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 0)["age_max"] = 28


def _overlap_in_ages(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 0)["age_max"] = 31


def _bands_start_late(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 0)["age_min"] = 5


def _last_band_closed(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 30)["age_max"] = 99


def _bands_differ_between_events(data: dict[str, Any]) -> None:
    # whtr M splits at 25/26 while pushups M splits at 29/30.
    young = _find(data, "whtr", "M", 0)
    old = _find(data, "whtr", "M", 30)
    young["age_max"] = 25
    old["age_min"] = 26


def _unknown_event(data: dict[str, Any]) -> None:
    _find(data, "whtr", "F", 30)["event"] = "swim"


def _event_in_two_components(data: dict[str, Any]) -> None:
    data["components"]["body_comp"]["events"].append("pushups")


def _missing_minimum(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 0)["component_minimum"] = None


def _unexpected_minimum(data: dict[str, Any]) -> None:
    _find(data, "whtr", "M", 0)["component_minimum"] = 55


def _minimum_not_a_row(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 0)["component_minimum"] = 11


def _points_above_component_max(data: dict[str, Any]) -> None:
    _find(data, "pushups", "M", 0)["brackets"][0]["points"] = 15.5


@pytest.mark.parametrize(
    "edit",
    [
        _drop_table,
        _gap_in_ages,
        _overlap_in_ages,
        _bands_start_late,
        _last_band_closed,
        _bands_differ_between_events,
        _unknown_event,
        _event_in_two_components,
        _missing_minimum,
        _unexpected_minimum,
        _minimum_not_a_row,
        _points_above_component_max,
    ],
)
def test_rejects_coverage_and_consistency_errors(
    standards_dict: dict[str, Any], edit: Edit
) -> None:
    edit(standards_dict)
    with pytest.raises(ValidationError):
        _parse(standards_dict)


def test_rejects_missing_sex(standards_dict: dict[str, Any]) -> None:
    standards_dict["tables"] = [t for t in standards_dict["tables"] if t["sex"] != "F"]
    with pytest.raises(ValidationError, match="missing table"):
        _parse(standards_dict)


def test_rejects_age_max_below_age_min(standards_dict: dict[str, Any]) -> None:
    table = _find(standards_dict, "pushups", "M", 0)
    table["age_min"], table["age_max"] = 29, 0
    with pytest.raises(ValidationError, match="below age_min"):
        _parse(standards_dict)


@pytest.mark.parametrize(
    ("event", "brackets"),
    [
        # higher is better: thresholds must fall as we go down the chart
        ("pushups", [{"threshold": 20, "points": 15.0}, {"threshold": 30, "points": 10.0}]),
        ("pushups", [{"threshold": 30, "points": 15.0}, {"threshold": 30, "points": 10.0}]),
        # lower is better: thresholds must rise as we go down the chart
        ("whtr", [{"threshold": 50, "points": 20.0}, {"threshold": 45, "points": 10.0}]),
        # points must fall too
        ("pushups", [{"threshold": 30, "points": 10.0}, {"threshold": 20, "points": 10.0}]),
        ("pushups", [{"threshold": 30, "points": 5.0}, {"threshold": 20, "points": 10.0}]),
    ],
)
def test_rejects_non_monotonic_brackets(
    standards_dict: dict[str, Any], event: str, brackets: list[dict[str, Any]]
) -> None:
    table = _find(standards_dict, event, "M", 0)
    table["brackets"] = brackets
    # keep the minimum valid so only the ordering rule can fail
    table["component_minimum"] = brackets[-1]["threshold"] if event == "pushups" else None
    with pytest.raises(ValidationError, match="strictly ordered"):
        _parse(standards_dict)


def test_rejects_empty_brackets(standards_dict: dict[str, Any]) -> None:
    _find(standards_dict, "whtr", "M", 0)["brackets"] = []
    with pytest.raises(ValidationError):
        _parse(standards_dict)


def test_parsed_file_is_frozen(standards_dict: dict[str, Any]) -> None:
    standards = parse_standards(json.dumps(standards_dict))
    with pytest.raises(ValidationError):
        standards.passing_total = 60
