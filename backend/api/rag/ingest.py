"""Upload pipeline: extract -> chunk -> injection scan -> embed -> store."""
from pathlib import Path

from . import injection, store
from .chunking import chunk_pages
from .extraction import extract_pages


def ingest_document(document, path: Path):
    pages = extract_pages(path)
    chunks = chunk_pages(pages)
    for chunk in chunks:
        chunk["flags"] = injection.scan(chunk["text"])
    store.add_chunks(document.id, document.name, chunks)

    document.pages = len(pages)
    document.chunks = len(chunks)
    document.flagged_chunks = sum(1 for c in chunks if c["flags"])
    document.status = "ready" if chunks else "empty"
    if not chunks:
        document.error = "No extractable text (scanned PDFs need OCR, which is out of scope)."
    document.save()
    return document
