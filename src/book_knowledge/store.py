"""Qdrant client, collection setup, and shared embedding helpers.

Uses FastEmbed (bundled with qdrant-client[fastembed]) so dense + sparse
embeddings run locally on CPU with no API keys.
"""
from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient, models

from .config import settings


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        check_compatibility=False,
    )


@lru_cache(maxsize=1)
def _dense_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=settings.dense_model)


@lru_cache(maxsize=1)
def _sparse_model():
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name=settings.sparse_model)


@lru_cache(maxsize=1)
def _dense_dim() -> int:
    # Embed a trivial string once to learn the vector size.
    vec = next(iter(_dense_model().embed(["dimension probe"])))
    return len(vec)


def embed_dense(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _dense_model().embed(texts)]


def embed_sparse(texts: list[str]) -> list[models.SparseVector]:
    out: list[models.SparseVector] = []
    for s in _sparse_model().embed(texts):
        out.append(models.SparseVector(indices=s.indices.tolist(), values=s.values.tolist()))
    return out


def ensure_collection() -> None:
    """Create the shared collection with named dense + sparse vectors if absent."""
    client = get_client()
    if client.collection_exists(settings.collection):
        return
    client.create_collection(
        collection_name=settings.collection,
        vectors_config={
            settings.dense_vector_name: models.VectorParams(
                size=_dense_dim(), distance=models.Distance.COSINE
            )
        },
        sparse_vectors_config={
            settings.sparse_vector_name: models.SparseVectorParams(
                modifier=models.Modifier.IDF
            )
        },
    )
    # Indexes that make metadata filtering fast.
    for field_name in ("book", "author", "chapter", "heading", "tags"):
        client.create_payload_index(
            collection_name=settings.collection,
            field_name=field_name,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
