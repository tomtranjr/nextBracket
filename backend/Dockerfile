# Two stages: the builder installs dependencies, the runtime image only copies the result.
# This keeps uv and its cache out of the final image.
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /bin/

# Compile bytecode for faster start. Copy files instead of linking, because the cache
# mount is not part of the image. Use the image Python, not a downloaded one.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Copy only the dependency files first. This layer stays cached until the lock changes.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project


FROM python:3.13-slim-bookworm AS runtime

# Same base as the builder, so the interpreter path inside .venv is still valid.
RUN useradd --system --create-home --uid 1000 app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# Only the app and the standards JSON. No tests, scripts, or source PDFs.
COPY app ./app
COPY data/standards ./data/standards

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

USER app
EXPOSE 8080

# `sh -c` so ${PORT} expands (Cloud Run sets PORT). `exec` replaces the shell with uvicorn,
# so uvicorn is PID 1, gets SIGTERM directly, and shuts down cleanly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
