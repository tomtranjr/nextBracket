"""In-memory rate limit for the public API.

The goal is to cap cost, not to meter users. Cloud Run runs at most one instance (see the deploy
workflow), so one process sees all traffic and a counter in memory is exact. If the instance
count goes above one, each instance counts alone and the limit is no longer exact.

The limiter keeps only a request count per client key for the current minute. It never stores or
logs the key beyond that, because the project stores no user data.
"""

import math
import time
from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

WINDOW_SECONDS = 60
# Upper bound on distinct keys held at once. Past this, new keys share one bucket,
# so a flood from many IPs cannot grow memory without bound.
MAX_KEYS = 10_000
OVERFLOW_KEY = "*"
# Cloud Run and the CI smoke test call this path. It must never be blocked.
EXEMPT_PATH = "/health"


class RateLimiter:
    """Fixed one-minute windows: one global count and one count per client key.

    A limit of 0 turns that limit off. The clock is a parameter so tests need no sleeping.
    A blocked request is not counted, so a blocked client does not use up the global allowance.
    """

    def __init__(
        self,
        per_key: int,
        global_limit: int,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = MAX_KEYS,
    ) -> None:
        self._per_key = per_key
        self._global_limit = global_limit
        self._clock = clock
        self._max_keys = max_keys
        self._window = -1
        self._global_count = 0
        self._counts: dict[str, int] = {}

    def check(self, key: str) -> int | None:
        """Count one request. Return None if allowed, else the seconds to wait."""
        now = self._clock()
        window = int(now // WINDOW_SECONDS)
        if window != self._window:
            # Every old count belongs to a finished window, so drop them all.
            self._window = window
            self._global_count = 0
            self._counts.clear()

        if key not in self._counts and len(self._counts) >= self._max_keys:
            key = OVERFLOW_KEY
        used = self._counts.get(key, 0)

        retry_after = max(1, math.ceil((window + 1) * WINDOW_SECONDS - now))
        if self._global_limit and self._global_count >= self._global_limit:
            return retry_after
        if self._per_key and used >= self._per_key:
            return retry_after

        self._global_count += 1
        self._counts[key] = used + 1
        return None


def client_key(scope: Scope) -> str:
    """Pick the key a request is counted under.

    Behind Cloud Run the front end appends the real client address as the LAST entry of
    `X-Forwarded-For`. Earlier entries come from the client and can be faked, so we ignore them.
    Without that header (local runs, tests) we use the socket address.
    """
    forwarded = ""
    for name, value in scope["headers"]:
        if name == b"x-forwarded-for":
            forwarded = value.decode("latin-1")
    last = forwarded.split(",")[-1].strip()
    if last:
        return last
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class RateLimitMiddleware:
    """Answer 429 with `Retry-After` when the limiter says no.

    This is a plain ASGI middleware, so it adds no per-request task. The event loop runs one
    request check at a time, so the limiter needs no lock.
    """

    def __init__(self, app: ASGIApp, limiter: RateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == EXEMPT_PATH:
            await self.app(scope, receive, send)
            return

        retry_after = self.limiter.check(client_key(scope))
        if retry_after is None:
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            {"detail": "Too many requests"},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
        await response(scope, receive, send)
