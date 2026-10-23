import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_standards_files
from app.core.lookup import get_standards
from app.core.planning import plan_to_target
from app.core.standards import parse_standards
from app.main import create_app
from app.models import PlanResult, Profile, Results, StandardsTable

REAL_DIR = Path(__file__).parents[1] / "data" / "standards"
PROFILE = {"age": 27, "sex": "M"}
CURRENT = {"run_2mile": 940, "push_up": 45, "sit_up": 50, "whtr": 49}


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Uses the real dependencies, so these tests read the committed charts."""
    with TestClient(create_app()) as c:
        yield c


def _plan(client: TestClient, **overrides: Any) -> Any:
    body = {"profile": PROFILE, "target": 90, "current": {"values": CURRENT}, **overrides}
    return client.post("/plan", json=body)


def _standards(client: TestClient, **overrides: Any) -> Any:
    return client.post("/standards", json={"profile": PROFILE, **overrides})


# /plan


def test_plan_matches_core(client: TestClient) -> None:
    response = _plan(client, target=95)
    assert response.status_code == 200
    standards = parse_standards((REAL_DIR / "2026-03-01.json").read_bytes())
    expected = plan_to_target(
        standards, Profile(age=27, sex="M"), 95, Results(values=CURRENT)
    ).model_dump(mode="json")
    assert response.json() == expected


def test_plan_response_parses_as_result(client: TestClient) -> None:
    PlanResult.model_validate_json(_plan(client, target=95).text)


def test_plan_without_current_assumes_minimums(client: TestClient) -> None:
    body = client.post("/plan", json={"profile": PROFILE, "target": 75}).json()
    assert body["status"] == "options"
    assert set(body["assumed_components"]) == {"cardio", "strength", "core", "body_comp"}


def test_plan_already_met(client: TestClient) -> None:
    body = _plan(client, target=1).json()
    assert body["status"] == "already_met"
    assert body["options"] == []


def test_plan_target_above_best_total_is_a_status_not_an_error(
    standards_dict: dict[str, Any],
) -> None:
    # The fixture file tops out at 35 points, so a target of 90 cannot be reached.
    app = create_app()
    app.dependency_overrides[get_standards_files] = lambda: [
        parse_standards(json.dumps(standards_dict))
    ]
    body = {"profile": PROFILE, "target": 90, "current": {"values": {"pushups": 25, "whtr": 45}}}
    response = TestClient(app).post("/plan", json=body)
    assert response.status_code == 200
    assert response.json()["status"] == "impossible"
    assert response.json()["max_total"] == 35


def test_plan_with_explicit_version(client: TestClient) -> None:
    assert _plan(client, version="2026-03-01").json()["version"] == "2026-03-01"


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": "nope"},
        {"current": {"values": {"not_an_event": 1}}},
        {"current": {"values": {"run_2mile": 940, "hamr_20m": 60}}},
        {"current": {"values": {"push_up": -1}}},
        {"target": -1},
        {"target": 101},
        {"profile": {"age": 16, "sex": "M"}},
        {"extra_key": 1},
    ],
    ids=[
        "unknown_version",
        "unknown_event",
        "two_events_one_component",
        "negative_result",
        "negative_target",
        "target_above_100",
        "age_too_low",
        "extra_key",
    ],
)
def test_plan_rejects_bad_input(client: TestClient, overrides: dict[str, Any]) -> None:
    assert _plan(client, **overrides).status_code == 422


@pytest.mark.parametrize("missing", ["profile", "target"])
def test_plan_rejects_missing_field(client: TestClient, missing: str) -> None:
    body: dict[str, Any] = {"profile": PROFILE, "target": 90}
    del body[missing]
    assert client.post("/plan", json=body).status_code == 422


def test_plan_rejects_string_target(client: TestClient) -> None:
    assert _plan(client, target="90").status_code == 422


# /standards


def test_standards_matches_core(client: TestClient) -> None:
    response = _standards(client)
    assert response.status_code == 200
    standards = parse_standards((REAL_DIR / "2026-03-01.json").read_bytes())
    expected = get_standards(standards, Profile(age=27, sex="M")).model_dump(mode="json")
    assert response.json() == expected


def test_standards_response_parses_as_table(client: TestClient) -> None:
    StandardsTable.model_validate_json(_standards(client).text)


def test_standards_lists_alternative_events_together(client: TestClient) -> None:
    body = _standards(client).json()
    cardio = next(c for c in body["components"] if c["component"] == "cardio")
    assert {t["event"] for t in cardio["tables"]} == {"run_2mile", "hamr_20m"}


def test_standards_for_one_event(client: TestClient) -> None:
    body = _standards(client, event="push_up").json()
    assert [c["component"] for c in body["components"]] == ["strength"]
    assert [t["event"] for c in body["components"] for t in c["tables"]] == ["push_up"]


def test_standards_picks_the_age_band(client: TestClient) -> None:
    young = _standards(client, profile={"age": 20, "sex": "F"}).json()
    old = _standards(client, profile={"age": 62, "sex": "F"}).json()
    assert young != old
    assert young["components"][0]["tables"][0]["age_min"] == 0
    assert old["components"][0]["tables"][0]["age_max"] is None


def test_standards_with_explicit_version(client: TestClient) -> None:
    assert _standards(client, version="2026-03-01").json()["version"] == "2026-03-01"


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": "nope"},
        {"event": "not_an_event"},
        {"profile": {"age": 71, "sex": "M"}},
        {"profile": {"age": 27, "sex": "X"}},
        {"extra_key": 1},
    ],
    ids=["unknown_version", "unknown_event", "age_too_high", "bad_sex", "extra_key"],
)
def test_standards_rejects_bad_input(client: TestClient, overrides: dict[str, Any]) -> None:
    assert _standards(client, **overrides).status_code == 422


def test_standards_rejects_missing_profile(client: TestClient) -> None:
    assert client.post("/standards", json={}).status_code == 422


def test_unknown_event_message(client: TestClient) -> None:
    assert "unknown event" in _standards(client, event="nope").json()["detail"]


# 2 km walk


def test_plan_with_walk_is_422(client: TestClient) -> None:
    current = {"walk_2km": 900, "push_up": 45, "sit_up": 50, "whtr": 49}
    response = _plan(client, current={"values": current})
    assert response.status_code == 422
    assert "2 km walk is not supported" in response.json()["detail"]


def test_standards_include_the_walk_row(client: TestClient) -> None:
    body = _standards(client, profile={"age": 45, "sex": "F"}).json()
    assert body["walk"] == {"sex": "F", "age_min": 40, "age_max": 49, "max_time": 1069}


def test_standards_walk_only(client: TestClient) -> None:
    body = _standards(client, event="walk_2km").json()
    assert body["components"] == []
    assert body["walk"]["max_time"] == 976


def test_standards_scored_event_has_no_walk(client: TestClient) -> None:
    assert _standards(client, event="push_up").json()["walk"] is None
