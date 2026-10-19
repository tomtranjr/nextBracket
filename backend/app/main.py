from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ratelimit import RateLimiter, RateLimitMiddleware
from app.api.routes import router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    # Settings are a parameter so a test can pass its own origins without touching the environment.
    settings = settings or get_settings()
    app = FastAPI(title="Next Bracket")
    # Added before CORS on purpose. The last middleware added is the outermost, so CORS wraps
    # the limiter and a 429 still carries CORS headers. Then the website can read it.
    if settings.rate_limit_per_ip or settings.rate_limit_global:
        limiter = RateLimiter(settings.rate_limit_per_ip, settings.rate_limit_global)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
    # The API is stateless and uses no cookies, so credentials stay off. Only the methods and
    # header the website uses are allowed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    app.include_router(router)
    return app


app = create_app()
