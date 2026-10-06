# Next Bracket

PFA scoring and planning for Airmen.

Next Bracket helps Air Force members see what they scored on the Physical Fitness Readiness Assessment, what they need to pass or hit a target, and what DAFMAN 36-2905 says. Every number comes from code. Every policy answer cites a paragraph.

This is an unofficial tool. It is not affiliated with the Air Force. Confirm results with your Fitness Assessment Cell.

## Status

Work in progress. Only the project setup is done. Nothing is scored yet.

Planned parts:

- a calculator that scores results from the official charts (effective 1 Mar 26)
- a planner that shows what you need to reach a target score
- a chat assistant that answers policy questions with paragraph citations
- a printable report

Nothing a user types is stored.

## Run the checks

You need [uv](https://docs.astral.sh/uv/).

```
cd backend
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests
uv run pytest
```

## Docs

- `nextBracket-design-doc.md`: the full design
- `CLAUDE.md`: short project rules for AI coding agents
