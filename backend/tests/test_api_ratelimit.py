from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ratelimit import MAX_KEYS, OVERFLOW_KEY, RateLimiter, RateLimitMiddleware
from app.config import Settings
from app.main import create_app

SITE = "http://localhost:3000"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


# --- the limiter on its own ---


def test_blocks_after_the_per_key_limit_and_resets_next_window() -> None:
    clock = FakeClock()
    limiter = RateLimiter(per_key=3, global_limit=0, clock=clock)
    assert [limiter.check("a") for _ in range(3)] == [None, None, None]
    retry = limiter.check("a")
    assert retry is not None
    assert 1 <= retry <= 60
    clock.now += 60
    assert limiter.check("a") is None


def test_keys_have_separate_counters() -> None:
    limiter = RateLimiter(per_key=1, global_limit=0, clock=FakeClock())
    assert limiter.check("a") is None
    assert limiter.check("a") is not None
    assert limiter.check("b") is None


def test_global_limit_blocks_even_when_each_key_is_under_its_limit() -> None:
    limiter = RateLimiter(per_key=5, global_limit=3, clock=FakeClock())
    assert [limiter.check(k) for k in "abc"] == [None, None, None]
    assert limiter.check("d") is not None


def test_a_blocked_request_is_not_counted() -> None:
    limiter = RateLimiter(per_key=1, global_limit=2, clock=FakeClock())
    assert limiter.check("a") is None
    for _ in range(10):
        assert limiter.check("a") is not None
    # The ten blocked calls did not use the global allowance.
    assert limiter.check("b") is None


def test_zero_turns_a_limit_off() -> None:
    limiter = RateLimiter(per_key=0, global_limit=0, clock=FakeClock())
    assert all(limiter.check("a") is None for _ in range(1000))


def test_retry_after_is_the_time_left_in_the_window() -> None:
    clock = FakeClock()
    clock.now = 1_000.0  # window runs from 960 to 1020
    limiter = RateLimiter(per_key=1, global_limit=0, clock=clock)
    limiter.check("a")
    assert limiter.check("a") == 20


def test_key_table_stays_bounded() -> None:
    limiter = RateLimiter(per_key=2, global_limit=0, clock=FakeClock(), max_keys=3)
    for key in "abc":
        assert limiter.check(key) is None
    # Table is full. New keys share one bucket, so the third request from any of them is blocked.
    assert limiter.check("x") is None
    assert limiter.check("y") is None
    assert limiter.check("z") is not None
    assert len(limiter._counts) == 4  # three keys plus the shared bucket
    assert OVERFLOW_KEY in limiter._counts
    assert MAX_KEYS >= 1000  # the real cap is far above normal use


# --- the middleware ---


def _app(limiter: RateLimiter) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/thing")
    def thing() -> dict[str, str]:
        return {"ok": "yes"}

    return app


@pytest.fixture
def small() -> Iterator[TestClient]:
    limiter = RateLimiter(per_key=2, global_limit=0, clock=FakeClock())
    with TestClient(_app(limiter)) as c:
        yield c


def test_third_request_gets_429_with_retry_after(small: TestClient) -> None:
    assert small.get("/thing").status_code == 200
    assert small.get("/thing").status_code == 200
    response = small.get("/thing")
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests"}
    assert int(response.headers["retry-after"]) >= 1


def test_health_is_never_limited(small: TestClient) -> None:
    for _ in range(10):
        assert small.get("/health").status_code == 200
    # And health calls did not use the allowance.
    assert small.get("/thing").status_code == 200


def test_different_forwarded_addresses_are_counted_apart(small: TestClient) -> None:
    for _ in range(2):
        small.get("/thing", headers={"X-Forwarded-For": "1.1.1.1"})
    assert small.get("/thing", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert small.get("/thing", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_a_faked_first_forwarded_entry_does_not_change_the_key(small: TestClient) -> None:
    # Cloud Run appends the real address last. The client can only fake what comes before it.
    for i in range(2):
        small.get("/thing", headers={"X-Forwarded-For": f"10.0.0.{i}, 9.9.9.9"})
    response = small.get("/thing", headers={"X-Forwarded-For": "10.0.0.99, 9.9.9.9"})
    assert response.status_code == 429


# --- wired into the real app ---


def test_app_answers_429_with_cors_headers() -> None:
    settings = Settings(rate_limit_per_ip=1, rate_limit_global=0)
    with TestClient(create_app(settings)) as client:
        # Three calls, so one window change between them cannot hide the block.
        responses = [client.get("/versions", headers={"Origin": SITE}) for _ in range(3)]
    blocked = [r for r in responses if r.status_code == 429]
    assert blocked
    assert blocked[0].headers["access-control-allow-origin"] == SITE
    assert "retry-after" in blocked[0].headers


def test_app_has_no_limiter_when_both_limits_are_off() -> None:
    settings = Settings(rate_limit_per_ip=0, rate_limit_global=0)
    with TestClient(create_app(settings)) as client:
        assert all(client.get("/versions").status_code != 429 for _ in range(100))
