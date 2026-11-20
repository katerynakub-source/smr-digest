"""PDF reports: text extraction (Readwise Reader-style reading mode)."""
import io
import re

from pypdf import PdfReader


def pdf_bytes_to_text(data: bytes, max_pages: int = 300) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:max_pages]:
        t = page.extract_text() or ""
        # re-flow hard-wrapped lines into paragraphs
        t = re.sub(r"-\n(\w)", r"\1", t)
        t = re.sub(r"(?<![.!?:;])\n(?!\n)", " ", t)
        pages.append(t.strip())
    text = "\n\n".join(p for p in pages if p)
    return re.sub(r"[ \t]+", " ", text)


def pdf_title(data: bytes, fallback: str) -> str:
    try:
        meta = PdfReader(io.BytesIO(data)).metadata
        if meta and meta.title and len(meta.title.strip()) > 3:
            return meta.title.strip()
    except Exception:
        pass
    return fallback
