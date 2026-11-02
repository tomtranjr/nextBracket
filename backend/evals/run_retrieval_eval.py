"""Retrieval eval over the AFMAN 36-2905 paragraph chunks.

Scores any search function with the shape `(query, k) -> list[paragraph]` against the
hand-written questions in `evals/retrieval.jsonl`. It reports recall@k and MRR@k.

Run from `backend/`:

    uv run python -m evals.run_retrieval_eval
"""

import argparse
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
CHUNKS_PATH = EVALS_DIR.parent / "data" / "regulation" / "chunks.jsonl"
CASES_PATH = EVALS_DIR / "retrieval.jsonl"
RESULTS_DIR = EVALS_DIR / "results"
K = 5  # The Design Doc sets retrieval to top 5 (section 6.2).

# A search function takes a query and k, and returns paragraph numbers, best first.
SearchFn = Callable[[str, int], list[str]]


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    # Any one of these paragraphs answers the question. The first one found counts.
    expected: tuple[str, ...]
    topic: str


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            cases.append(
                EvalCase(
                    id=row["id"],
                    question=row["question"],
                    expected=tuple(row["expected"]),
                    topic=row["topic"],
                )
            )
    return cases


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def first_hit_rank(results: Sequence[str], expected: Sequence[str]) -> int | None:
    """Return the 1-based rank of the first expected paragraph, or None if none is found."""
    for rank, paragraph in enumerate(results, start=1):
        if paragraph in expected:
            return rank
    return None


def evaluate(search: SearchFn, cases: Sequence[EvalCase], k: int = K) -> dict[str, Any]:
    """Run every case through `search` and return the metrics and the rank for each case.

    recall@k is the share of cases with an expected paragraph in the top k.
    MRR@k is the mean of 1 / rank of the first hit, with 0 when the top k has no hit.
    """
    if not cases:
        raise ValueError("no eval cases")
    per_case = []
    hits = 0
    reciprocal_sum = 0.0
    for case in cases:
        # Cut to k so a search that returns extra results gains nothing.
        top = search(case.question, k)[:k]
        rank = first_hit_rank(top, case.expected)
        if rank is not None:
            hits += 1
            reciprocal_sum += 1 / rank
        per_case.append({"id": case.id, "rank": rank, "top": top})
    return {
        "k": k,
        "cases": len(cases),
        "recall_at_k": round(hits / len(cases), 4),
        "mrr_at_k": round(reciprocal_sum / len(cases), 4),
        "per_case": per_case,
    }


# --- Baseline: keyword overlap ---------------------------------------------------------

# Common words that match almost every chunk and say nothing about the topic.
STOPWORDS = frozenset(
    """
    a an and are as at be been but by can could do does did for from had has have how i if in
    into is it its just me my of on or so still than that the their them then there they this
    to up was we were what when where which who why will with would you your am im dont
    """.split()
)


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS}


def keyword_search(chunks: Sequence[dict[str, Any]]) -> SearchFn:
    """Build a search that ranks chunks by how many query words they share.

    The title is included because a sub-paragraph's title is its parent's run-in heading.
    Ties keep document order, so the ranking is the same on every run.
    """
    index = [(c["paragraph"], tokenize(f"{c['title']} {c['text']}")) for c in chunks]

    def search(query: str, k: int) -> list[str]:
        words = tokenize(query)
        scored = [(len(words & tokens), i, p) for i, (p, tokens) in enumerate(index)]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [p for _, _, p in scored[:k]]

    return search


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "retrieval_keyword_baseline.json",
        help="where to write the results JSON",
    )
    args = parser.parse_args(argv)

    chunks = load_chunks()
    report = {
        "search": "keyword_overlap",
        "chunks_version": chunks[0]["version"],
        **evaluate(keyword_search(chunks), load_cases()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"{report['search']}: recall@{report['k']} = {report['recall_at_k']:.3f}, "
        f"MRR@{report['k']} = {report['mrr_at_k']:.3f} over {report['cases']} cases"
    )


if __name__ == "__main__":
    main()
