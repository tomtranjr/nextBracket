from typing import Any

import pytest


def _table(
    event: str,
    sex: str,
    age_min: int,
    age_max: int | None,
    higher_is_better: bool,
    brackets: list[tuple[int, float]],
    component_minimum: int | None,
) -> dict[str, Any]:
    return {
        "sex": sex,
        "age_min": age_min,
        "age_max": age_max,
        "event": event,
        "unit": "reps" if higher_is_better else "seconds",
        "higher_is_better": higher_is_better,
        "component_minimum": component_minimum,
        "brackets": [{"threshold": t, "points": p} for t, p in brackets],
    }


@pytest.fixture
def standards_dict() -> dict[str, Any]:
    """A tiny hand-written standards file. The numbers are FAKE and only exercise the schema.

    Two components (one with a minimum, one without), two sexes, two age bands. Each test gets
    a fresh copy, so tests can edit it to break one rule at a time.
    """
    tables: list[dict[str, Any]] = []
    for sex in ("M", "F"):
        for age_min, age_max in ((0, 29), (30, None)):
            tables.append(
                _table(
                    "pushups", sex, age_min, age_max, True, [(30, 15.0), (20, 10.0), (10, 5.0)], 10
                )
            )
            tables.append(
                _table(
                    "whtr", sex, age_min, age_max, False, [(45, 20.0), (50, 10.0), (55, 4.0)], None
                )
            )
    return {
        "version": "test",
        "effective_date": "2026-03-01",
        "source": "hand-written test fixture",
        "passing_total": 75,
        "components": {
            "strength": {"max_points": 15, "has_minimum": True, "events": ["pushups"]},
            "body_comp": {"max_points": 20, "has_minimum": False, "events": ["whtr"]},
        },
        "afspecwar_eod": {"sex": "M", "age_min": 0, "events": ["pushups"]},
        "tables": tables,
    }
