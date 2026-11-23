"""Load `data/regulation/chunks.jsonl` into Postgres with pgvector.

Run from `backend/`, with the `db` service from docker-compose.yml up and `OPENAI_API_KEY` set:

    uv run python -m scripts.ingest_regulation

It embeds every chunk with OpenAI `text-embedding-3-small`, then upserts the rows in one
transaction. It is a one-off script. Rerun it only when a new regulation issue is published.
A rerun of the same issue replaces its rows and deletes paragraphs that are no longer in the file.

The target database is `NEXTBRACKET_DATABASE_URL` (default: the local compose database).
"""

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

# app.rag.embedding is shared with app/rag/search.py, so chunk and query vectors match.
from app.config import get_settings
from app.rag.embedding import EMBEDDING_DIM, Embedder, openai_embedder, to_vector_literal

BACKEND = Path(__file__).resolve().parent.parent
# Written by scripts/extract_regulation.py. Not imported from there, because that module
# imports pdfplumber, a dev-only dependency.
DEFAULT_CHUNKS = BACKEND / "data" / "regulation" / "chunks.jsonl"
SCHEMA_PATH = BACKEND / "scripts" / "regulation_schema.sql"

# The API takes up to 2048 inputs per call. 100 keeps each request small; the corpus needs 7.
BATCH_SIZE = 100


@dataclass(frozen=True)
class Chunk:
    paragraph: str
    title: str
    text: str
    source_doc: str
    version: str
    page: int


def load_chunks(path: Path = DEFAULT_CHUNKS) -> list[Chunk]:
    with path.open(encoding="utf-8") as f:
        return [Chunk(**json.loads(line)) for line in f if line.strip()]


def embedding_input(chunk: Chunk) -> str:
    # Many chunks are short sub-paragraphs whose title comes from a parent ("3.7.1" under
    # "Cardiorespiratory"). Putting the title first gives the vector that missing context.
    return f"{chunk.title}\n{chunk.text}"


def embed_all(
    texts: Sequence[str], embed: Embedder, batch_size: int = BATCH_SIZE
) -> list[list[float]]:
    """Embed `texts` in batches. Fails loudly on a wrong count or size instead of storing it."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        out = embed(batch)
        if len(out) != len(batch):
            raise ValueError(f"embedder returned {len(out)} vectors for {len(batch)} texts")
        for vector in out:
            if len(vector) != EMBEDDING_DIM:
                raise ValueError(f"expected {EMBEDDING_DIM} numbers, got {len(vector)}")
        vectors.extend(out)
    return vectors


UPSERT_SQL = """
INSERT INTO regulation_chunks (source_doc, version, paragraph, title, text, page, embedding)
VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
ON CONFLICT (source_doc, version, paragraph) DO UPDATE SET
    title = EXCLUDED.title,
    text = EXCLUDED.text,
    page = EXCLUDED.page,
    embedding = EXCLUDED.embedding
"""

# A paragraph that the extractor no longer writes must not stay behind as a stale answer.
DELETE_STALE_SQL = """
DELETE FROM regulation_chunks
WHERE source_doc = %s AND version = %s AND NOT (paragraph = ANY(%s))
"""


def ingest(conn: psycopg.Connection[Any], chunks: Sequence[Chunk], embed: Embedder) -> int:
    """Create the schema, upsert every chunk, and drop stale paragraphs. Returns the row count.

    The caller owns the transaction, so a failure part way leaves the old rows in place.
    """
    if not chunks:
        raise ValueError("no chunks to ingest")
    issues = {(c.source_doc, c.version) for c in chunks}
    if len(issues) != 1:
        raise ValueError(f"expected one source_doc and version, got {sorted(issues)}")
    (source_doc, version) = issues.pop()
    # The upsert keeps only the last copy of a repeated paragraph, so a duplicate would lose text.
    counts = Counter(c.paragraph for c in chunks)
    duplicates = sorted(p for p, n in counts.items() if n > 1)
    if duplicates:
        raise ValueError(f"duplicate paragraphs: {duplicates}")

    # Embed before touching the database, so an OpenAI error changes nothing.
    vectors = embed_all([embedding_input(c) for c in chunks], embed)

    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        cur.executemany(
            UPSERT_SQL,
            [
                (
                    c.source_doc,
                    c.version,
                    c.paragraph,
                    c.title,
                    c.text,
                    c.page,
                    to_vector_literal(v),
                )
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )
        cur.execute(DELETE_STALE_SQL, (source_doc, version, [c.paragraph for c in chunks]))
        cur.execute(
            "SELECT count(*) FROM regulation_chunks WHERE source_doc = %s AND version = %s",
            (source_doc, version),
        )
        row = cur.fetchone()
    assert row is not None
    count: int = row[0]
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    args = parser.parse_args()

    chunks = load_chunks(args.chunks)
    # `with` commits on success and rolls back on an error.
    with psycopg.connect(get_settings().database_url) as conn:
        count = ingest(conn, chunks, openai_embedder())
    print(f"Loaded {count} rows for {chunks[0].source_doc} {chunks[0].version}.")


if __name__ == "__main__":
    main()
