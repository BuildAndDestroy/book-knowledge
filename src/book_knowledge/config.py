"""Central configuration, read from environment (.env supported)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    qdrant_url: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str | None = os.environ.get("QDRANT_API_KEY") or None
    collection: str = os.environ.get("BOOK_COLLECTION", "books")

    dense_model: str = os.environ.get("DENSE_MODEL", "BAAI/bge-small-en-v1.5")
    sparse_model: str = os.environ.get("SPARSE_MODEL", "Qdrant/bm25")
    rerank_model: str = os.environ.get("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")

    chunk_size: int = _int("CHUNK_SIZE", 1800)
    chunk_overlap: int = _int("CHUNK_OVERLAP", 200)

    # Named vectors inside the collection.
    dense_vector_name: str = "dense"
    sparse_vector_name: str = "sparse"


settings = Settings()
