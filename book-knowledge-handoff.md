# Project brief: Book knowledge base for agents

## Goal
Use books as knowledge for AI agents across multiple projects/GitHub repos, without loading whole PDFs into every session. Starting with 1 book, planning to scale to many.

## Decided architecture (centralized, shared by all repos)

1. **Ingestion pipeline** (one command per book)
   - PDF → Markdown (`marker`, `docling`, or `pymupdf4llm`)
   - Split by chapter/section (not fixed token counts)
   - Embed → upsert into Qdrant
   - CLI shape: `ingest book.pdf --tags sales,negotiation`

2. **Qdrant (shared store)**
   - ONE collection; payload metadata: `book`, `author`, `chapter`, `heading`, `tags`
   - Hybrid search (dense + sparse/BM25) from day one; add a reranker
   - Run via Docker Compose on a machine I control (or Qdrant Cloud)

3. **One MCP server, used by every repo**
   - `search(query, books?, tags?)` – hybrid search with metadata filters
   - `list_books()`
   - `get_section(book, chapter)` – read a full section after search locates it
   - Each repo's `.mcp.json` points to the same server; per-repo default books/tags via env var or config

4. **Distilled skills per book**
   - Short `SKILL.md` with the book's core frameworks, checklists, and when to apply them
   - Pointer to the MCP `search` tool for detail
   - Kept in one central skills repo, installed user-level or as a plugin so all projects stay in sync

## Build order
1. Ingestion script + Qdrant (Docker Compose); tune chunking/search on the first book
2. MCP server (Python) with `search` and `get_section`, then `list_books`
3. First distilled skill
4. Wire into one repo, then roll out

## First task for Claude Code
Scaffold the starter kit: `docker-compose.yml` for Qdrant, the ingestion script, and the Python MCP server, with a README covering setup and adding a book.
