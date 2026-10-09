"""Turn course documents into (text, metadata) pages.

One record per page/slide so citations can point at "Lecture 2, slide 14".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Page:
    text: str
    source: str   # file name shown in citations
    page: int     # 1-based page or slide number


def _clean(text: str) -> str:
    return " ".join(text.split())


def load_pdf(path: Path) -> list[Page]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, p in enumerate(reader.pages, start=1):
        text = _clean(p.extract_text() or "")
        if text:
            pages.append(Page(text, path.name, i))
    return pages


def load_pptx(path: Path) -> list[Page]:
    from pptx import Presentation

    prs = Presentation(str(path))
    pages = []
    for i, slide in enumerate(prs.slides, start=1):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
        if slide.has_notes_slide:
            parts.append(slide.notes_slide.notes_text_frame.text)
        text = _clean("\n".join(parts))
        if text:
            pages.append(Page(text, path.name, i))
    return pages


def load_docx(path: Path) -> list[Page]:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    text = _clean("\n".join(parts))
    return [Page(text, path.name, 1)] if text else []


def load_text(path: Path) -> list[Page]:
    text = _clean(path.read_text(encoding="utf-8", errors="ignore"))
    return [Page(text, path.name, 1)] if text else []


_LOADERS = {
    ".pdf": load_pdf,
    ".pptx": load_pptx,
    ".docx": load_docx,
    ".txt": load_text,
    ".md": load_text,
}


def load_document(path: Path) -> list[Page]:
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"unsupported file type: {path.suffix}")
    return loader(path)
