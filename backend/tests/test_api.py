import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_standards_files, get_today, load_standards_dir
from app.core.scoring import calculate_score
from app.core.standards import parse_standards
from app.main import create_app
from app.models import Profile, Results, ScoreReport, StandardsFile

REAL_DIR = Path(__file__).parents[1] / "data" / "standards"
FULL = {"run_2mile": 940, "push_up": 45, "sit_up": 50, "whtr": 49}
PROFILE = {"age": 27, "sex": "M"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Uses the real dependencies, so these tests read the committed charts."""
    with TestClient(create_app()) as c:
        yield c


def _score(client: TestClient, **overrides: Any) -> Any:
    body = {"profile": PROFILE, "results": {"values": FULL}, **overrides}
    return client.post("/score", json=body)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_versions_lists_real_charts(client: TestClient) -> None:
    body = client.get("/versions").json()
    assert body["default"] == "2026-03-01"
    assert [v["version"] for v in body["versions"]] == ["2026-03-01"]
    assert body["versions"][0]["effective_date"] == "2026-03-01"


def test_score_matches_core(client: TestClient) -> None:
    response = _score(client)
    assert response.status_code == 200
    standards = parse_standards((REAL_DIR / "2026-03-01.json").read_bytes())
    expected = calculate_score(
        standards, Profile(age=27, sex="M"), Results(values=FULL)
    ).model_dump(mode="json")
    assert response.json() == expected


def test_score_with_explicit_version(client: TestClient) -> None:
    assert _score(client, version="2026-03-01").json()["version"] == "2026-03-01"


def test_partial_results_have_no_total(client: TestClient) -> None:
    response = _score(client, results={"values": {"run_2mile": 940}})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] is None
    assert body["category"] is None
    assert set(body["not_scored"]) == {"strength", "core", "body_comp"}


def test_score_response_parses_as_report(client: TestClient) -> None:
    # JSON mode, because strict models do not accept a date string in Python mode.
    ScoreReport.model_validate_json(_score(client).text)


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": "nope"},
        {"results": {"values": {"not_an_event": 1}}},
        {"results": {"values": {"run_2mile": 940, "hamr_20m": 60}}},
        {"results": {"values": {"push_up": -1}}},
        {"profile": {"age": 16, "sex": "M"}},
        {"profile": {"age": 71, "sex": "M"}},
        {"profile": {"age": 27, "sex": "X"}},
        {"extra_key": 1},
    ],
    ids=[
        "unknown_version",
        "unknown_event",
        "two_events_one_component",
        "negative_result",
        "age_too_low",
        "age_too_high",
        "bad_sex",
        "extra_key",
    ],
)
def test_score_rejects_bad_input(client: TestClient, overrides: dict[str, Any]) -> None:
    assert _score(client, **overrides).status_code == 422


def test_score_rejects_missing_profile(client: TestClient) -> None:
    response = client.post("/score", json={"results": {"values": FULL}})
    assert response.status_code == 422


def test_unknown_version_message(client: TestClient) -> None:
    assert "unknown standards version" in _score(client, version="nope").json()["detail"]


def _file(standards_dict: dict[str, Any], version: str, effective: str) -> StandardsFile:
    data = {**standards_dict, "version": version, "effective_date": effective}
    return parse_standards(json.dumps(data))


def _override(files: list[StandardsFile], today: date) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_standards_files] = lambda: files
    app.dependency_overrides[get_today] = lambda: today
    return TestClient(app)


def test_default_version_ignores_future_file(standards_dict: dict[str, Any]) -> None:
    files = [
        _file(standards_dict, "old", "2025-01-01"),
        _file(standards_dict, "current", "2026-01-01"),
        _file(standards_dict, "future", "2027-01-01"),
    ]
    client = _override(files, date(2026, 3, 1))
    assert client.get("/versions").json()["default"] == "current"
    body = {"profile": PROFILE, "results": {"values": {"pushups": 25, "whtr": 45}}}
    assert client.post("/score", json=body).json()["version"] == "current"
    assert client.post("/score", json={**body, "version": "future"}).json()["version"] == "future"


def test_versions_unavailable_when_nothing_in_force(standards_dict: dict[str, Any]) -> None:
    client = _override([_file(standards_dict, "future", "2027-01-01")], date(2026, 3, 1))
    assert client.get("/versions").status_code == 503


def test_load_standards_dir_reads_real_charts() -> None:
    assert [f.version for f in load_standards_dir(REAL_DIR)] == ["2026-03-01"]


def test_load_standards_dir_rejects_empty_folder(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no standards files"):
        load_standards_dir(tmp_path)


def test_load_standards_dir_rejects_duplicate_versions(
    tmp_path: Path, standards_dict: dict[str, Any]
) -> None:
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text(json.dumps(standards_dict))
    with pytest.raises(ValueError, match="duplicate standards versions"):
        load_standards_dir(tmp_path)
