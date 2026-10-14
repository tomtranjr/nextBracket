from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SITE = "http://localhost:3000"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def _preflight(client: TestClient, origin: str, path: str = "/score") -> dict[str, str]:
    response = client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return dict(response.headers)


def test_preflight_allows_the_local_site(client: TestClient) -> None:
    headers = _preflight(client, SITE)
    assert headers["access-control-allow-origin"] == SITE
    assert "POST" in headers["access-control-allow-methods"]


def test_preflight_blocks_other_origins(client: TestClient) -> None:
    assert "access-control-allow-origin" not in _preflight(client, "http://evil.test")


def test_actual_response_carries_the_header(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": SITE})
    assert response.headers["access-control-allow-origin"] == SITE


def test_credentials_are_not_allowed(client: TestClient) -> None:
    assert "access-control-allow-credentials" not in _preflight(client, SITE)


def test_custom_origins_replace_the_default() -> None:
    settings = Settings(cors_origins=["https://example.app"])
    with TestClient(create_app(settings)) as c:
        assert _preflight(c, "https://example.app")["access-control-allow-origin"] == (
            "https://example.app"
        )
        assert "access-control-allow-origin" not in _preflight(c, SITE)


def test_origins_come_from_a_json_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXTBRACKET_CORS_ORIGINS", '["https://a.app", "https://b.app"]')
    assert Settings().cors_origins == ["https://a.app", "https://b.app"]
