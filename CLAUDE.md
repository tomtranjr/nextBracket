# Next Bracket

PFA scoring and planning for Airmen. A stateless web app: a calculator, a cited policy chatbot, and a printable report. This file is the short version of the project rules.

## Work tracking

Work is tracked in Linear (team `NB`). Read the issue named in your task and the Agent Guide document in the Linear project before you start. Source data facts are in `docs/developer-guide.md`.

## Principles

1. The LLM never computes a score. All numbers come from tested Python functions.
2. Add a component only when an eval shows it is needed, then report before and after.
3. Every answer is traceable: scores to a chart version, policy to a paragraph.
4. Form first, chat second. The calculator must work with no LLM.

## Layout

```
backend/
  app/core/       scoring, planning, standards lookup (pure functions, no I/O)
  app/rag/        retrieval over pgvector
  app/agent/      LangGraph graph, thin tool wrappers, prompt
  app/api/        FastAPI routers
  app/models.py   Pydantic schemas shared everywhere
  data/standards/ versioned scoring JSON
  data/sources/   official PDFs (charts committed, DAFMAN git-ignored)
  scripts/        extraction and ingestion scripts
  tests/  evals/
frontend/         Next.js, TypeScript, Tailwind
  app/            routes and layout (App Router)
  lib/            API client, API types, time parsing
```

Check the Linear project for what is built.

## Commands (run in `backend/`)

```
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests
uv run pytest
uv run uvicorn app.main:app --reload   # run the API locally
```

Frontend commands (run in `frontend/`, Node version in `.nvmrc`):

```
npm ci
npm run lint && npm run typecheck && npm test && npm run build
npm run dev                            # run the site locally
```

Pre-commit hooks (run at the repo root, config in `.pre-commit-config.yaml`):

```
uvx pre-commit install                 # once per clone
uvx pre-commit run --all-files
```

CI runs these checks on every push: the four backend checks, the pre-commit hygiene hooks, the Docker smoke test, and the frontend checks.

## Rules

- Never invent scoring values. If a value is unknown, leave a marked placeholder and a failing test, and flag it.
- Chart values come from `scripts/extract_tables.py`, then are checked by hand against the PDF.
- Keep `app/core/` free of I/O and LLM calls. Tools in `app/agent/` are thin wrappers around `core`.
- Do not add new dependencies without asking. No new infrastructure.
- Never log request bodies or user inputs. Never store user inputs. Never send user inputs to Vercel Web Analytics or Speed Insights. They record page views and performance only, with no custom events.
- Write tests with the code. Type hints everywhere. Ruff and mypy must pass.
- Explain non-obvious decisions in short code comments.
- Units are integers: reps, shuttles, seconds. WHtR is stored in hundredths.
- WHtR from a waist and height is truncated to two decimals, never rounded (DAFMAN 36-2905 para 3.15.4.2).
- Python 3.13, managed with uv. Frontend packages are managed with npm.
- `frontend/lib/types.ts` mirrors `backend/app/models.py` by hand. Change both together.
- `frontend/lib/events.ts` mirrors the event keys in `backend/data/standards/` by hand. A Vitest test checks it.
- `NEXT_PUBLIC_*` values reach the browser. Never put a secret in one.
