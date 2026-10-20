# Follows the uv Docker guide and its multistage example:
# https://docs.astral.sh/uv/guides/integration/docker/
# Two stages: the builder has uv and installs the project. The runtime image has no uv.

# The derived uv image has uv and Python preinstalled. The uv version is pinned.
# The digest pins the exact image, so a moved tag cannot change a build.
FROM ghcr.io/astral-sh/uv:0.13.0-python3.13-trixie-slim@sha256:40215b626e22e4ff65839863624c4b885b8829b1a66ce895b7be20eca7fabe6d AS builder

# Compile bytecode for faster start. Copy files instead of linking, because the cache
# mount is not part of the image. Skip dev dependencies. Use the system Python in both
# stages, not a downloaded one.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first. The bind mounts expose the lock files to this one step
# without copying them into a layer, so this layer stays cached until they change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# .dockerignore decides what this copies. Then sync again, so the lock is checked
# against the full project.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


# The final image has no uv.
FROM python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
# This must match the builder's Python, because .venv points at the interpreter path.

RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# No --chown: the files stay owned by root, so the app cannot change its own code.
# The API writes no files.
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

USER nonroot
WORKDIR /app
EXPOSE 8080

# `sh -c` so ${PORT} expands (Cloud Run sets PORT). `exec` replaces the shell with uvicorn,
# so uvicorn is PID 1, gets SIGTERM directly, and shuts down cleanly.
# We use uvicorn, not `fastapi run`, because fastapi-cli is not a dependency.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
