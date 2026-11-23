"""Two baseline searches over `regulation_chunks`: full text only, and vector only.

They exist to give the retrieval eval two numbers to beat. Hybrid search (NB-6) combines them.
Each function takes an open connection and returns hits best first. Neither one logs the query.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import psycopg

from app.rag.embedding import EMBEDDING_DIM, to_vector_literal


@dataclass(frozen=True)
class SearchHit:
    paragraph: str
    title: str
    text: str
    page: int
    # Higher is better. The scale differs by method, so compare scores only within one method.
    score: float


# plainto_tsquery joins every word with AND (&). A plain question rarely has all its words in
# one paragraph, so an AND query often finds nothing. Swapping & for | makes it match any word,
# and ts_rank then puts paragraphs with more and rarer matches first. plainto_tsquery never
# emits other operators, so the text swap is safe. Title words count more (weight A, see
# scripts/regulation_schema.sql). Ties sort by paragraph, so the order is stable.
FULL_TEXT_SQL = """
WITH q AS (
    SELECT replace(plainto_tsquery('english', %(query)s)::text, '&', '|')::tsquery AS tsq
)
SELECT paragraph, title, text, page, ts_rank(tsv, q.tsq) AS score
FROM regulation_chunks, q
WHERE source_doc = %(source_doc)s AND version = %(version)s AND tsv @@ q.tsq
ORDER BY score DESC, paragraph
LIMIT %(k)s
"""

# <=> is pgvector cosine distance (0 is the same direction, 2 is opposite). 1 - distance is
# cosine similarity, so a higher score is a better match like the full-text score.
# With no vector index this is an exact scan, so it never misses a closer chunk.
VECTOR_SQL = """
SELECT paragraph, title, text, page, 1 - (embedding <=> %(vec)s::vector) AS score
FROM regulation_chunks
WHERE source_doc = %(source_doc)s AND version = %(version)s
ORDER BY embedding <=> %(vec)s::vector, paragraph
LIMIT %(k)s
"""


def _check_k(k: int) -> None:
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")


def _hits(rows: Sequence[tuple[Any, ...]]) -> list[SearchHit]:
    return [
        SearchHit(paragraph=p, title=t, text=x, page=pg, score=float(s)) for p, t, x, pg, s in rows
    ]


def full_text_search(
    conn: psycopg.Connection[Any], query: str, k: int, *, source_doc: str, version: str
) -> list[SearchHit]:
    """Rank paragraphs by Postgres full-text match on any query word. Returns at most k hits.

    A query with only stopwords ("is it the") matches nothing and returns an empty list.
    """
    _check_k(k)
    params = {"query": query, "source_doc": source_doc, "version": version, "k": k}
    return _hits(conn.execute(FULL_TEXT_SQL, params).fetchall())


def vector_search(
    conn: psycopg.Connection[Any],
    query_vector: Sequence[float],
    k: int,
    *,
    source_doc: str,
    version: str,
) -> list[SearchHit]:
    """Rank paragraphs by cosine similarity to `query_vector`. Returns at most k hits.

    The caller embeds the query, so this function needs no OpenAI client and tests can pass
    any vector.
    """
    _check_k(k)
    if len(query_vector) != EMBEDDING_DIM:
        raise ValueError(f"expected {EMBEDDING_DIM} numbers, got {len(query_vector)}")
    params = {
        "vec": to_vector_literal(query_vector),
        "source_doc": source_doc,
        "version": version,
        "k": k,
    }
    return _hits(conn.execute(VECTOR_SQL, params).fetchall())
