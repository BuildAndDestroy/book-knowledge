# 📚 Book Knowledge Base

Turn books (PDFs) into a shared, searchable knowledge base your AI agents can query —
instead of stuffing whole PDFs into every session.

One Qdrant database holds **every** book. One small MCP server lets **any** repo
search it. Everything runs locally on your machine — no API keys, nothing leaves
your computer.

```
   your PDF ──▶ Markdown ──▶ smart chunks ──▶ Qdrant (hybrid search)
                                                    │
         any repo / agent ◀── MCP server (3 tools) ◀┘
```

---

## Quickstart (5 steps)

You need **Docker** and **Python 3.10+**. That's it.

### 1. Start the database

```bash
docker compose up -d
```

Qdrant is now running. Open the dashboard at **http://localhost:6333/dashboard** to
see your data any time.

### 2. Install the toolkit

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[rerank]'
cp .env.example .env
```

> The first install downloads a few hundred MB (the local search models). Grab a coffee ☕.

### 3. Add a book

Drop a PDF you own in `books/` (books are **not** shipped with this repo — bring your own; the folder is git-ignored), then:

```bash
ingest books/your-book.pdf --tags topic1,topic2
```

The title and author are read from the PDF automatically. Tags are optional labels
you can filter by later (e.g. `sales`, `security`, `cooking`).

### 4. Search it

```bash
book-search "how does X work"
```

That's it — you're searching the book. Add `--rerank` for more precise results
(a little slower), or `--limit 10` for more hits.

### 5. (Optional) Let your agents use it

Point any repo's `.mcp.json` at the server (see [Using it from your repos](#using-it-from-your-repos)).

---

## The three commands

| Command | What it does | Example |
|---------|--------------|---------|
| `ingest` | Add a book to the knowledge base | `ingest books/book.pdf --tags security` |
| `book-search` | Search from your terminal | `book-search "AMSI bypass" --rerank` |
| `book-mcp` | Run the server agents connect to | `book-mcp` |

> Run these from inside the virtualenv (`source .venv/bin/activate`).

### `ingest` options

```bash
ingest books/book.pdf \
  --tags malware,evasion     # comma-separated labels
  --book "Custom Title"      # override the auto-detected title
  --author "Jane Doe"        # override the auto-detected author
```

Re-running the same book is safe — it updates in place instead of duplicating.

### `book-search` options

```bash
book-search "your question"
  --limit 5                  # how many results (default 5)
  --rerank                   # higher-precision reranking (slower)
  --book "Some Title"        # only search within one book (repeatable)
  --tag security             # only search chunks with this tag (repeatable)
  --json                     # machine-readable output
```

**Example:**

```bash
book-search "registry run key persistence" --tag malware --limit 3
```

---

## Using it from your repos

Every repo talks to the **same** server, so all your projects share one knowledge base.

1. Make sure Qdrant is running (`docker compose up -d`).
2. Add this to the repo's `.mcp.json` (a copy lives in [`examples/mcp.json`](examples/mcp.json)):

```json
{
  "mcpServers": {
    "book-knowledge": {
      "command": "/path/to/book-knowledge/.venv/bin/book-mcp",
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "DEFAULT_TAGS": "malware,redteam"
      }
    }
  }
}
```

`DEFAULT_TAGS` / `DEFAULT_BOOKS` scope searches to what *that* repo cares about, so
the agent doesn't have to specify them every time.

The agent then gets three tools:

| Tool | Purpose |
|------|---------|
| `search(query, books?, tags?, limit?, rerank?)` | Find relevant passages |
| `list_books()` | See what's in the knowledge base |
| `get_section(book, chapter)` | Pull a full section after search finds it |

---

## Configuration

All settings live in `.env` (copied from `.env.example`). Sensible defaults are
built in — you only touch this if you want to change something.

| Setting | Default | What it controls |
|---------|---------|------------------|
| `QDRANT_URL` | `http://localhost:6333` | Where Qdrant lives |
| `BOOK_COLLECTION` | `books` | Database collection name |
| `DENSE_MODEL` | `BAAI/bge-small-en-v1.5` | Meaning-based search model |
| `SPARSE_MODEL` | `Qdrant/bm25` | Keyword-based search model |
| `RERANK_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | Reranker (used with `--rerank`) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1800` / `200` | How books are split up (characters) |
| `DEFAULT_BOOKS` / `DEFAULT_TAGS` | — | Per-repo search defaults (for MCP) |

**Hybrid search** means two engines run together: a *dense* model that understands
meaning ("process injection" finds "code injection techniques") and a *sparse* model
that nails exact keywords (acronyms, API names). Results are merged — you get the best
of both.

---

## Troubleshooting

**`ingest` says "No module named pymupdf4llm" / the install looks broken.**
A bad `pymupdf4llm` release (2.0) is empty on PyPI. The pinned version in
`pyproject.toml` avoids it. If you hit it, run `pip install -e .` again.

**Search returns nothing.**
Check a book is actually loaded: `book-search --help` runs, and the dashboard at
http://localhost:6333/dashboard should show points under the `books` collection.
If it's empty, re-run `ingest`.

**"Connection refused" / can't reach Qdrant.**
Qdrant isn't running. `docker compose up -d`, then `docker compose ps` to confirm.

**Results feel off.**
Add `--rerank`. If still weak, the PDF may have extracted poorly — see the note below.

**A chapter name looks wrong (e.g. just a number).**
Some PDFs (especially ones without a table of contents) have messy heading data, so
chapter labels are best-effort. Search itself is unaffected. For cleaner structure on a
tough PDF, swap the extractor in `src/book_knowledge/pdf_to_markdown.py` for `marker` or
`docling` (heavier, may want a GPU).

---

## How it's laid out

```
docker-compose.yml        Qdrant database service
pyproject.toml            dependencies + the 3 commands
.env.example              settings template
examples/mcp.json         drop-in config for your repos
books/                    put your PDFs here
data/                     database files + extracted text (auto-created)
src/book_knowledge/
  config.py               reads your .env
  pdf_to_markdown.py      PDF  ->  Markdown
  chunk.py                splits books into searchable pieces
  store.py                talks to Qdrant + runs the search models
  ingest.py               the `ingest` command
  search.py               the `book-search` command + search logic
  mcp_server.py           the `book-mcp` server
```

---

## Adding more books

Just repeat step 3 for each PDF. They all go into the same collection and are
searchable together, or individually with `--book`:

```bash
ingest books/negotiation.pdf --tags sales,negotiation
ingest books/cooking.pdf --tags recipes
book-search "closing techniques" --tag sales
```
