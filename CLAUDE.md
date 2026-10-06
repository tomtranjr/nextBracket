# Next Bracket

PFA scoring and planning for Airmen. A stateless web app: a calculator, a cited policy chatbot, and a printable report. Full detail is in `nextBracket-design-doc.md`. This file is the short version.

## Build plan

If `_tmp/build-plan.md` exists, read it before starting work. It lists the PRs in order and their status. Update it when a PR starts or merges, and whenever we change the plan. Add a dated line to its Changes log.

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
frontend/         Next.js (later)
```

Only `backend/` exists so far. Check the build plan for what is built.

## Commands (run in `backend/`)

```
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests
uv run pytest
```

CI runs the same four checks on every push.

## Rules

- Never invent scoring values. If a value is unknown, leave a marked placeholder and a failing test, and flag it.
- Chart values come from `scripts/extract_tables.py`, then are checked by hand against the PDF.
- Keep `app/core/` free of I/O and LLM calls. Tools in `app/agent/` are thin wrappers around `core`.
- Do not add dependencies outside the design doc (section 5) without asking. No new infrastructure.
- Never log request bodies or user inputs. Never store user data.
- Write tests with the code. Type hints everywhere. Ruff and mypy must pass.
- Explain non-obvious decisions in short code comments.
- Units are integers: reps, shuttles, seconds. WHtR is stored in hundredths.
- Python 3.13, managed with uv.
