"""MCP server exposing the shared book knowledge base.

Tools:
  - search(query, books?, tags?, limit?, rerank?)
  - list_books()
  - get_section(book, chapter)

Every repo points its .mcp.json at this one server. Per-repo defaults come from
DEFAULT_BOOKS / DEFAULT_TAGS in the environment.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from . import search as retrieval

mcp = FastMCP("book-knowledge")


def _env_list(name: str) -> list[str] | None:
    raw = os.environ.get(name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] or None


_DEFAULT_BOOKS = _env_list("DEFAULT_BOOKS")
_DEFAULT_TAGS = _env_list("DEFAULT_TAGS")


@mcp.tool()
def search(
    query: str,
    books: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 5,
    rerank: bool = False,
) -> list[dict]:
    """Hybrid (dense + sparse) search across ingested books.

    Args:
        query: Natural-language question or keywords.
        books: Restrict to these book titles. Defaults to this repo's books.
        tags: Restrict to these tags. Defaults to this repo's tags.
        limit: Max results to return.
        rerank: Apply cross-encoder reranking for higher precision (slower).
    """
    return retrieval.search(
        query,
        books=books or _DEFAULT_BOOKS,
        tags=tags or _DEFAULT_TAGS,
        limit=limit,
        rerank=rerank,
    )


@mcp.tool()
def list_books() -> list[dict]:
    """List the books available in the knowledge base with chunk counts."""
    return retrieval.list_books()


@mcp.tool()
def get_section(book: str, chapter: str) -> str:
    """Return the full text of a chapter/section after search has located it."""
    return retrieval.get_section(book, chapter)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
