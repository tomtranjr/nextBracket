import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from app.config import get_settings


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

    Two components (one with a minimum, one without), two sexes, two age bands. The walk has
    its own two bands per sex (0-39 and 40+), which differ from the scoring bands on purpose.
    Each test gets a fresh copy, so tests can edit it to break one rule at a time.
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
        "chart_name": "Test Scoring Charts",
        "passing_total": 75,
        "components": {
            "strength": {"max_points": 15, "has_minimum": True, "events": ["pushups"]},
            "body_comp": {"max_points": 20, "has_minimum": False, "events": ["whtr"]},
        },
        "afspecwar_eod": {"sex": "M", "age_min": 0, "events": ["pushups"]},
        "tables": tables,
        "walk": [
            {"sex": sex, "age_min": age_min, "age_max": age_max, "max_time": max_time}
            for sex, offset in (("M", 0), ("F", 60))
            for age_min, age_max, max_time in ((0, 39, 960 + offset), (40, None, 1000 + offset))
        ],
    }


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    """A connection whose tables live in a throwaway schema, so real rows are never touched."""
    try:
        connection = psycopg.connect(get_settings().database_url, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Postgres is not running (start it with `docker compose up db`)")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with connection:
        # The extension lives in public, so the vector type resolves from the test schema too.
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")
        connection.execute(f"CREATE SCHEMA {schema}")
        connection.execute(f"SET search_path TO {schema}, public")
        # Commit the setup, so the teardown rollback undoes only what the test did.
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.execute(f"DROP SCHEMA {schema} CASCADE")
            connection.commit()
