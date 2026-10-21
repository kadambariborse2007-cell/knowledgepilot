"""Extract text from PDF/TXT files while keeping page numbers."""
from pathlib import Path

from pypdf import PdfReader


def extract_pages(path: Path) -> list[dict]:
    """Return a list of {"page": int, "text": str}. Pages are 1-based."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": number, "text": text})
        return pages

    if suffix == ".txt":
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        # A form-feed character is treated as a page break; otherwise the whole file is page 1.
        parts = text.split("\f")
        return [{"page": i, "text": part} for i, part in enumerate(parts, start=1)]

    raise ValueError(f"Unsupported file type: {suffix}")
