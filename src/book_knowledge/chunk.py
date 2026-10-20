"""Split Markdown into retrieval chunks.

Strategy: split by Markdown headings into sections (so chapters/sections stay
coherent), then sub-split any section that exceeds the chunk budget, keeping a
small character overlap so context isn't lost across a boundary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# A trailing lone page number that PDF-extracted headings sometimes carry.
_TRAILING_NUM_RE = re.compile(r"\s+\d{1,4}$")


def _clean_heading(text: str) -> str:
    # Drop control characters that leak out of PDF extraction, collapse spaces,
    # then strip a trailing lone page number.
    text = "".join(ch for ch in text if ch >= " " or ch == "\t")
    text = re.sub(r"\s+", " ", text).strip()
    return _TRAILING_NUM_RE.sub("", text).strip()


def _looks_like_title(text: str) -> bool:
    """A real section/chapter title, not a bare number or page-header fragment."""
    t = text.strip()
    return len(t) >= 4 and not t.isdigit()


@dataclass
class Section:
    heading: str  # nearest heading text ("" before the first heading)
    level: int  # heading level (0 before the first heading)
    chapter: str  # nearest level-1/2 heading, used as the "chapter" label
    text: str


@dataclass
class Chunk:
    text: str
    heading: str
    chapter: str
    section_index: int
    chunk_index: int  # index within the section
    meta: dict = field(default_factory=dict)


def split_sections(markdown: str) -> list[Section]:
    """Walk the markdown line by line, grouping body text under its heading."""
    sections: list[Section] = []
    heading, level, chapter = "", 0, ""
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append(Section(heading=heading, level=level, chapter=chapter, text=text))

    for line in markdown.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            flush()
            buf = []
            level = len(m.group(1))
            heading = _clean_heading(m.group(2))
            # Track the nearest real title as the "chapter" grouping. Heading
            # levels are font-size-driven in many PDFs, so we rely on the text
            # looking like a title rather than on the level number.
            if _looks_like_title(heading):
                chapter = heading
        else:
            buf.append(line)
    flush()
    return sections


def _subsplit(text: str, size: int, overlap: int) -> list[str]:
    """Greedy split on paragraph boundaries, falling back to hard slices."""
    if len(text) <= size:
        return [text]

    paras = re.split(r"\n\s*\n", text)
    parts: list[str] = []
    cur = ""
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if len(para) > size:
            # A single huge paragraph: hard-slice it with overlap.
            if cur:
                parts.append(cur)
                cur = ""
            start = 0
            while start < len(para):
                parts.append(para[start : start + size])
                start += size - overlap
            continue
        if len(cur) + len(para) + 2 <= size:
            cur = f"{cur}\n\n{para}" if cur else para
        else:
            parts.append(cur)
            # start next chunk with a tail of the previous one for continuity
            tail = cur[-overlap:] if overlap and cur else ""
            cur = f"{tail}\n\n{para}" if tail else para
    if cur:
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def chunk_markdown(markdown: str, size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for s_idx, section in enumerate(split_sections(markdown)):
        for c_idx, piece in enumerate(_subsplit(section.text, size, overlap)):
            # Prepend the heading so each chunk carries its own context.
            text = f"# {section.heading}\n\n{piece}" if section.heading else piece
            chunks.append(
                Chunk(
                    text=text,
                    heading=section.heading,
                    chapter=section.chapter,
                    section_index=s_idx,
                    chunk_index=c_idx,
                )
            )
    return chunks
