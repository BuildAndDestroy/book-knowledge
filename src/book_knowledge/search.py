"""Hybrid retrieval over the shared book collection.

Dense + sparse via Qdrant's Query API with Reciprocal Rank Fusion, optional
metadata filters (books / tags), and an optional cross-encoder reranker.
"""
from __future__ import annotations

import json
from functools import lru_cache

import typer
from qdrant_client import models

from .config import settings
from .store import embed_dense, embed_sparse, get_client


def _filter(books: list[str] | None, tags: list[str] | None) -> models.Filter | None:
    must: list[models.FieldCondition] = []
    if books:
        must.append(models.FieldCondition(key="book", match=models.MatchAny(any=books)))
    if tags:
        must.append(models.FieldCondition(key="tags", match=models.MatchAny(any=tags)))
    return models.Filter(must=must) if must else None


@lru_cache(maxsize=1)
def _reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=settings.rerank_model)


def search(
    query: str,
    books: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 5,
    rerank: bool = False,
    candidate_multiplier: int = 4,
) -> list[dict]:
    """Return a ranked list of chunk hits with payload + score."""
    client = get_client()
    qf = _filter(books, tags)
    prefetch_n = max(limit * candidate_multiplier, 20)

    dense_q = embed_dense([query])[0]
    sparse_q = embed_sparse([query])[0]

    fetch = limit * candidate_multiplier if rerank else limit
    res = client.query_points(
        collection_name=settings.collection,
        prefetch=[
            models.Prefetch(
                query=dense_q,
                using=settings.dense_vector_name,
                filter=qf,
                limit=prefetch_n,
            ),
            models.Prefetch(
                query=sparse_q,
                using=settings.sparse_vector_name,
                filter=qf,
                limit=prefetch_n,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=fetch,
        with_payload=True,
    ).points

    hits = [
        {
            "score": p.score,
            "book": (p.payload or {}).get("book"),
            "author": (p.payload or {}).get("author"),
            "chapter": (p.payload or {}).get("chapter"),
            "heading": (p.payload or {}).get("heading"),
            "tags": (p.payload or {}).get("tags"),
            "text": (p.payload or {}).get("text", ""),
        }
        for p in res
    ]

    if rerank and hits:
        scores = list(_reranker().rerank(query, [h["text"] for h in hits]))
        for h, s in zip(hits, scores):
            h["rerank_score"] = float(s)
        hits.sort(key=lambda h: h["rerank_score"], reverse=True)

    return hits[:limit]


def list_books() -> list[dict]:
    """Distinct books in the collection with chunk counts."""
    client = get_client()
    books: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.collection,
            with_payload=["book", "author"],
            with_vectors=False,
            limit=512,
            offset=offset,
        )
        for p in points:
            b = (p.payload or {}).get("book")
            if not b:
                continue
            entry = books.setdefault(b, {"book": b, "author": (p.payload or {}).get("author"), "chunks": 0})
            entry["chunks"] += 1
        if offset is None:
            break
    return sorted(books.values(), key=lambda e: e["book"])


def get_section(book: str, chapter: str) -> str:
    """Reassemble the full text of a chapter/section from its stored chunks."""
    client = get_client()
    qf = models.Filter(
        must=[
            models.FieldCondition(key="book", match=models.MatchValue(value=book)),
            # Nested OR: match the title against either the chapter or heading field.
            models.Filter(
                should=[
                    models.FieldCondition(key="chapter", match=models.MatchValue(value=chapter)),
                    models.FieldCondition(key="heading", match=models.MatchValue(value=chapter)),
                ]
            ),
        ]
    )
    collected: list[tuple[int, int, str]] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.collection,
            scroll_filter=qf,
            with_payload=True,
            with_vectors=False,
            limit=512,
            offset=offset,
        )
        for p in points:
            pl = p.payload or {}
            collected.append((pl.get("section_index", 0), pl.get("chunk_index", 0), pl.get("text", "")))
        if offset is None:
            break
    collected.sort(key=lambda t: (t[0], t[1]))
    return "\n\n".join(t[2] for t in collected)


def main(
    query: str = typer.Argument(..., help="Search query."),
    book: list[str] = typer.Option(None, "--book", help="Restrict to a book (repeatable)."),
    tag: list[str] = typer.Option(None, "--tag", help="Restrict to a tag (repeatable)."),
    limit: int = typer.Option(5, help="Number of results."),
    rerank: bool = typer.Option(False, help="Apply cross-encoder reranking."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    hits = search(query, books=book or None, tags=tag or None, limit=limit, rerank=rerank)
    if as_json:
        typer.echo(json.dumps(hits, indent=2))
        return
    for i, h in enumerate(hits, 1):
        typer.echo(f"\n[{i}] {h['book']} — {h['chapter'] or h['heading']}  (score {h['score']:.4f})")
        snippet = h["text"].strip().replace("\n", " ")
        typer.echo(f"    {snippet[:300]}...")


def cli() -> None:
    typer.run(main)


if __name__ == "__main__":
    cli()
