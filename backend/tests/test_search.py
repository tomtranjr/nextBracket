"""Tests for app/rag/search.py. None of them call OpenAI.

The database tests use the `conn` fixture from conftest.py. They skip when Postgres is not
reachable, so CI (which has no Postgres) skips them.
"""

from typing import Any

import psycopg
import pytest

from app.rag.embedding import EMBEDDING_DIM
from app.rag.search import full_text_search, vector_search
from scripts.ingest_regulation import Chunk, ingest, load_chunks

DOC = "AFMAN 36-2905"
VERSION = "2026-03-24"


def unit_vector(axis: int) -> list[float]:
    """A vector that points along one axis, so cosine order is easy to predict."""
    vector = [0.0] * EMBEDDING_DIM
    vector[axis] = 1.0
    return vector


def chunk(paragraph: str, title: str, text: str, version: str = VERSION) -> Chunk:
    return Chunk(
        paragraph=paragraph, title=title, text=text, source_doc=DOC, version=version, page=1
    )


def embed_by_paragraph(axes: dict[str, int]) -> Any:
    """Build a fake embedder that maps each chunk to the axis of its paragraph.

    The ingest input is "title\\ntext", so the fake reads the text back to find the chunk.
    """

    def embed(texts: list[str]) -> list[list[float]]:
        return [unit_vector(axes[t.split("\n", 1)[1]]) for t in texts]

    return embed


SMALL = [
    chunk("1.1", "Retest", "A member who fails may retest after 90 days."),
    chunk("1.2", "Walk", "The 2 km walk replaces the run for some members."),
    chunk("1.3", "Plank", "Hold the forearm plank as long as possible."),
]


@pytest.fixture
def small_db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    # Text -> axis. 1.1 on axis 0, 1.2 on axis 1, 1.3 on axis 2.
    axes = {c.text: i for i, c in enumerate(SMALL)}
    ingest(conn, SMALL, embed_by_paragraph(axes))
    return conn


# Input checks. These raise before any SQL, so they need no database.


def test_k_below_one_is_rejected() -> None:
    db: Any = None
    with pytest.raises(ValueError, match="k must be at least 1"):
        full_text_search(db, "retest", 0, source_doc=DOC, version=VERSION)
    with pytest.raises(ValueError, match="k must be at least 1"):
        vector_search(db, unit_vector(0), 0, source_doc=DOC, version=VERSION)


def test_vector_of_the_wrong_size_is_rejected() -> None:
    db: Any = None
    with pytest.raises(ValueError, match=f"expected {EMBEDDING_DIM} numbers"):
        vector_search(db, [1.0, 0.0], 5, source_doc=DOC, version=VERSION)


# Full text


def test_full_text_matches_any_word_not_all_words(small_db: psycopg.Connection[Any]) -> None:
    # "airmen" is in no chunk. An AND query would return nothing; the OR query still finds 1.1.
    hits = full_text_search(small_db, "Can airmen retest?", 5, source_doc=DOC, version=VERSION)
    assert [h.paragraph for h in hits] == ["1.1"]
    assert hits[0].title == "Retest" and hits[0].page == 1 and hits[0].score > 0


def test_full_text_ranks_more_matches_first(small_db: psycopg.Connection[Any]) -> None:
    hits = full_text_search(small_db, "walk instead of the run", 5, source_doc=DOC, version=VERSION)
    assert hits[0].paragraph == "1.2"
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_full_text_with_only_stopwords_finds_nothing(small_db: psycopg.Connection[Any]) -> None:
    assert full_text_search(small_db, "is it the", 5, source_doc=DOC, version=VERSION) == []


def test_full_text_stays_in_one_version(small_db: psycopg.Connection[Any]) -> None:
    ingest(
        small_db,
        [chunk("9.9", "Retest", "Retest rules.", "2027-01-01")],
        lambda t: [unit_vector(0) for _ in t],
    )
    hits = full_text_search(small_db, "retest", 5, source_doc=DOC, version=VERSION)
    assert "9.9" not in [h.paragraph for h in hits]


# Vector


def test_vector_ranks_by_cosine_similarity(small_db: psycopg.Connection[Any]) -> None:
    # Closest to axis 1 (1.2), then axis 0 (1.1), then axis 2 (1.3) at similarity 0.
    query = unit_vector(1)
    query[0] = 0.5
    hits = vector_search(small_db, query, 5, source_doc=DOC, version=VERSION)
    assert [h.paragraph for h in hits] == ["1.2", "1.1", "1.3"]
    assert hits[0].score == pytest.approx(1 / (1.25**0.5))
    assert hits[2].score == pytest.approx(0.0)


def test_vector_returns_at_most_k(small_db: psycopg.Connection[Any]) -> None:
    hits = vector_search(small_db, unit_vector(2), 1, source_doc=DOC, version=VERSION)
    assert [h.paragraph for h in hits] == ["1.3"]
    assert hits[0].score == pytest.approx(1.0)


# Real corpus. Fake vectors, so only full text says anything about relevance here.


def test_full_text_finds_the_whtr_truncation_paragraph(conn: psycopg.Connection[Any]) -> None:
    ingest(conn, load_chunks(), lambda texts: [unit_vector(0) for _ in texts])
    hits = full_text_search(
        conn, "Is my waist to height ratio rounded?", 5, source_doc=DOC, version=VERSION
    )
    assert len(hits) == 5
    assert "3.15.4.2" in [h.paragraph for h in hits]
