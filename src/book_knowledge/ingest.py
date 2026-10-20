"""Ingest a book PDF into the shared Qdrant collection.

    ingest path/to/book.pdf --tags malware,evasion
"""
from __future__ import annotations

import uuid
from pathlib import Path

import typer
from qdrant_client import models

from .chunk import chunk_markdown
from .config import settings
from .pdf_to_markdown import pdf_to_markdown
from .store import embed_dense, embed_sparse, ensure_collection, get_client

app = typer.Typer(add_completion=False, help="Ingest a book PDF into Qdrant.")

_NAMESPACE = uuid.UUID("b00c0b00-0000-4000-8000-000000000000")


def _pdf_metadata(pdf_path: Path) -> dict:
    try:
        import pymupdf  # provided by pymupdf4llm

        with pymupdf.open(str(pdf_path)) as doc:
            return dict(doc.metadata or {})
    except Exception:
        return {}


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


@app.command()
def main(
    pdf: Path = typer.Argument(..., exists=True, readable=True, help="Path to the book PDF."),
    book: str = typer.Option(None, help="Book title (defaults to PDF metadata or filename)."),
    author: str = typer.Option(None, help="Author (defaults to PDF metadata)."),
    tags: str = typer.Option("", help="Comma-separated tags applied to every chunk."),
    batch_size: int = typer.Option(64, help="Embedding/upsert batch size."),
    cache_markdown: bool = typer.Option(True, help="Save the extracted Markdown under data/markdown/."),
) -> None:
    meta = _pdf_metadata(pdf)
    book = book or meta.get("title") or pdf.stem.replace("_", " ")
    author = author or meta.get("author") or "Unknown"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    typer.echo(f"Book:   {book}")
    typer.echo(f"Author: {author}")
    typer.echo(f"Tags:   {tag_list or '(none)'}")

    typer.echo("Converting PDF -> Markdown (this can take a minute)...")
    markdown = pdf_to_markdown(pdf)

    if cache_markdown:
        out = Path("data/markdown")
        out.mkdir(parents=True, exist_ok=True)
        md_path = out / f"{_slug(book)}.md"
        md_path.write_text(markdown, encoding="utf-8")
        typer.echo(f"Saved Markdown -> {md_path}")

    chunks = chunk_markdown(markdown, size=settings.chunk_size, overlap=settings.chunk_overlap)
    typer.echo(f"Produced {len(chunks)} chunks. Ensuring collection '{settings.collection}'...")
    ensure_collection()
    client = get_client()

    total = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c.text for c in batch]
        dense = embed_dense(texts)
        sparse = embed_sparse(texts)
        points = []
        for c, d, s in zip(batch, dense, sparse):
            pid = str(
                uuid.uuid5(_NAMESPACE, f"{book}|{c.section_index}|{c.chunk_index}")
            )
            points.append(
                models.PointStruct(
                    id=pid,
                    vector={
                        settings.dense_vector_name: d,
                        settings.sparse_vector_name: s,
                    },
                    payload={
                        "book": book,
                        "author": author,
                        "chapter": c.chapter,
                        "heading": c.heading,
                        "tags": tag_list,
                        "section_index": c.section_index,
                        "chunk_index": c.chunk_index,
                        "text": c.text,
                    },
                )
            )
        client.upsert(collection_name=settings.collection, points=points)
        total += len(points)
        typer.echo(f"  upserted {total}/{len(chunks)}")

    typer.echo(f"Done. Ingested '{book}' ({total} chunks) into '{settings.collection}'.")


if __name__ == "__main__":
    app()
