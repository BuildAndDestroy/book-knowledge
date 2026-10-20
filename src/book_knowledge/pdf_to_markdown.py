"""PDF -> Markdown conversion using pymupdf4llm (CPU-only, no GPU needed)."""
from __future__ import annotations

from pathlib import Path


def pdf_to_markdown(pdf_path: str | Path) -> str:
    """Convert a PDF to GitHub-flavored Markdown, preserving heading structure."""
    import pymupdf4llm

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    # page_chunks=False returns one markdown string for the whole document.
    return pymupdf4llm.to_markdown(str(pdf_path), show_progress=True)
