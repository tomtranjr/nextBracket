"""Tests for scripts/ingest_regulation.py. None of them call OpenAI.

The unit tests need nothing. The database tests need the compose `db` service. They skip when it
is not reachable, so CI (which has no Postgres) skips them.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app.config import get_settings
from scripts.extract_regulation import DEFAULT_OUT
from scripts.ingest_regulation import (
    DEFAULT_CHUNKS,
    EMBEDDING_DIM,
    Chunk,
    embed_all,
    embedding_input,
    ingest,
    load_chunks,
    to_vector_literal,
)


def fake_embed(texts: list[str]) -> list[list[float]]:
    # A fixed vector per text length is enough: the tests check plumbing, not meaning.
    return [[float(len(t))] * EMBEDDING_DIM for t in texts]


def make_chunk(paragraph: str, text: str = "Some text.") -> Chunk:
    return Chunk(
        paragraph=paragraph,
        title="Title",
        text=text,
        source_doc="AFMAN 36-2905",
        version="2026-03-24",
        page=6,
    )


# Unit tests


def test_default_path_matches_the_extractor_output() -> None:
    assert DEFAULT_CHUNKS == DEFAULT_OUT


def test_load_chunks_reads_every_line_of_the_committed_file() -> None:
    chunks = load_chunks()
    with DEFAULT_CHUNKS.open(encoding="utf-8") as f:
        assert len(chunks) == sum(1 for _ in f)
    assert chunks[0].paragraph == "1.1"


def test_load_chunks_rejects_an_unknown_field(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    path.write_text('{"paragraph": "1.1", "surprise": 1}\n', encoding="utf-8")
    with pytest.raises(TypeError):
        load_chunks(path)


def test_embedding_input_puts_the_title_first() -> None:
    assert embedding_input(make_chunk("1.1", "Body.")) == "Title\nBody."


def test_embed_all_batches_and_keeps_order() -> None:
    calls: list[int] = []

    def embed(texts: list[str]) -> list[list[float]]:
        calls.append(len(texts))
        return fake_embed(texts)

    texts = ["a" * n for n in range(1, 8)]
    vectors = embed_all(texts, embed, batch_size=3)
    assert calls == [3, 3, 1]
    assert [v[0] for v in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_embed_all_fails_on_a_missing_vector() -> None:
    with pytest.raises(ValueError, match="2 vectors for 3 texts"):
        embed_all(["a", "b", "c"], lambda texts: fake_embed(texts)[:2])


def test_embed_all_fails_on_the_wrong_size() -> None:
    with pytest.raises(ValueError, match=f"expected {EMBEDDING_DIM} numbers, got 3"):
        embed_all(["a"], lambda texts: [[0.0, 0.0, 0.0]])


def test_vector_literal_is_the_pgvector_text_form() -> None:
    assert to_vector_literal([0.5, -1, 0.1]) == "[0.5,-1.0,0.1]"


def test_ingest_rejects_mixed_versions_before_any_sql() -> None:
    other = Chunk(**{**make_chunk("1.2").__dict__, "version": "2027-01-01"})
    # No connection is needed: the check runs first, so a None connection is never used.
    conn: Any = None
    with pytest.raises(ValueError, match="one source_doc and version"):
        ingest(conn, [make_chunk("1.1"), other], fake_embed)


# Database tests


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    """A connection whose tables live in a throwaway schema, so real rows are never touched."""
    try:
        connection = psycopg.connect(get_settings().database_url, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Postgres is not running (start it with `docker compose up db`)")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with connection:
        # The extension lives in public, so the vector type resolves from the test schema too.
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")
        connection.execute(f"CREATE SCHEMA {schema}")
        connection.execute(f"SET search_path TO {schema}, public")
        # Commit the setup, so the teardown rollback undoes only what the test did.
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.execute(f"DROP SCHEMA {schema} CASCADE")
            connection.commit()


def test_ingest_loads_every_committed_chunk(conn: psycopg.Connection[Any]) -> None:
    chunks = load_chunks()
    assert ingest(conn, chunks, fake_embed) == len(chunks)
    row = conn.execute(
        "SELECT title, page, vector_dims(embedding) FROM regulation_chunks WHERE paragraph = %s",
        ("3.15.4.2",),
    ).fetchone()
    assert row is not None
    assert row[1] > 0
    assert row[2] == EMBEDDING_DIM


def test_rerun_updates_rows_and_deletes_stale_paragraphs(conn: psycopg.Connection[Any]) -> None:
    ingest(conn, [make_chunk("1.1"), make_chunk("1.2")], fake_embed)
    count = ingest(conn, [make_chunk("1.1", "New text.")], fake_embed)
    assert count == 1
    rows = conn.execute("SELECT paragraph, text FROM regulation_chunks").fetchall()
    assert rows == [("1.1", "New text.")]


def test_full_text_index_finds_a_paragraph(conn: psycopg.Connection[Any]) -> None:
    ingest(conn, load_chunks(), fake_embed)
    rows = conn.execute(
        "SELECT paragraph FROM regulation_chunks WHERE tsv @@ plainto_tsquery('english', %s)",
        ("truncated decimal points",),
    ).fetchall()
    assert ("3.15.4.2",) in rows
