-- Regulation chunks with their embeddings. Reference data only, never user data.
-- scripts/ingest_regulation.py runs this file before each load. Every statement is safe to rerun.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS regulation_chunks (
    source_doc text NOT NULL,     -- "AFMAN 36-2905"
    version    text NOT NULL,     -- issue date of the regulation, "2026-03-24"
    paragraph  text NOT NULL,     -- "3.15.4.2", or "A3" for an attachment
    title      text NOT NULL,
    text       text NOT NULL,
    page       integer NOT NULL,  -- PDF page where the paragraph starts, for citations
    -- text-embedding-3-small returns 1536 numbers.
    embedding  vector(1536) NOT NULL,
    -- Full-text search document. A title match ranks above a body match (weight A over B).
    -- Postgres keeps it in step with title and text, so the script never writes it.
    tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', text), 'B')
    ) STORED,
    -- One row per paragraph per regulation issue. Older issues can stay for reference.
    PRIMARY KEY (source_doc, version, paragraph)
);

CREATE INDEX IF NOT EXISTS regulation_chunks_tsv_idx ON regulation_chunks USING gin (tsv);

-- No vector index. About 630 rows is small enough for an exact scan, which also has perfect
-- recall. Add HNSW only if a latency number shows it is needed.
