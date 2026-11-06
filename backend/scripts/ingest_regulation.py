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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from app.config import get_settings

BACKEND = Path(__file__).resolve().parent.parent
# Written by scripts/extract_regulation.py. Not imported from there, because that module
# imports pdfplumber, a dev-only dependency.
DEFAULT_CHUNKS = BACKEND / "data" / "regulation" / "chunks.jsonl"
SCHEMA_PATH = BACKEND / "scripts" / "regulation_schema.sql"

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # Must match vector(1536) in regulation_schema.sql.
# The API takes up to 2048 inputs per call. 100 keeps each request small; the corpus needs 7.
BATCH_SIZE = 100

# Takes a batch of texts and returns one vector per text, in the same order.
# Tests pass a fake, so they never call OpenAI.
Embedder = Callable[[list[str]], list[list[float]]]


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


def openai_embedder(model: str = EMBEDDING_MODEL) -> Embedder:
    # Imported here, so tests and the API never need an OpenAI key to import this module.
    from openai import OpenAI

    client = OpenAI()  # Reads OPENAI_API_KEY from the environment.

    def embed(texts: list[str]) -> list[list[float]]:
        response = client.embeddings.create(model=model, input=texts)
        # The API returns one item per input with an `index`. Sort on it, so the order is
        # certain and does not rely on the response order.
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]

    return embed


def to_vector_literal(vector: Sequence[float]) -> str:
    # pgvector reads the text form "[0.1,0.2,...]". With a `::vector` cast in the SQL, this
    # avoids the pgvector Python package. repr() keeps every digit of each float.
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


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
