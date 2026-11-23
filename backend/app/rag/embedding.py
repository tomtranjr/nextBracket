"""Text embeddings for the regulation corpus and for search queries.

Ingest and search share this module, because a query vector only compares with chunk vectors
made by the same model.
"""

from collections.abc import Callable, Sequence

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # Must match vector(1536) in scripts/regulation_schema.sql.

# Takes a batch of texts and returns one vector per text, in the same order.
# Tests pass a fake, so they never call OpenAI.
Embedder = Callable[[list[str]], list[list[float]]]


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
