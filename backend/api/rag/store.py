"""Chroma vector store wrapper."""
import threading

import chromadb
from django.conf import settings

from . import models

COLLECTION = "knowledgepilot_chunks"
_lock = threading.Lock()
_client = None
_version = 0


def _collection():
    global _client
    with _lock:
        if _client is None:
            _client = chromadb.PersistentClient(
                path=str(settings.CHROMA_DIR),
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
    return _client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def version() -> int:
    """Increases every time the stored chunks change (used to refresh the BM25 index)."""
    return _version


def add_chunks(document_id: int, file_name: str, chunks: list[dict]):
    global _version
    if not chunks:
        return
    collection = _collection()
    batch = 64
    for start in range(0, len(chunks), batch):
        part = chunks[start : start + batch]
        collection.add(
            ids=[f"{document_id}-{c['index']}" for c in part],
            documents=[c["text"] for c in part],
            embeddings=models.embed([c["text"] for c in part]),
            metadatas=[
                {
                    "document_id": document_id,
                    "file_name": file_name,
                    "page": c["page"],
                    "chunk_index": c["index"],
                    "flagged": bool(c.get("flags")),
                    "flags": "; ".join(c.get("flags", [])),
                }
                for c in part
            ],
        )
    _version += 1


def delete_document(document_id: int):
    global _version
    _collection().delete(where={"document_id": document_id})
    _version += 1


def _where(document_ids):
    if not document_ids:
        return None
    if len(document_ids) == 1:
        return {"document_id": document_ids[0]}
    return {"document_id": {"$in": list(document_ids)}}


def _to_chunk(chunk_id, text, meta, **extra):
    return {
        "id": chunk_id,
        "text": text,
        "document_id": meta["document_id"],
        "file_name": meta["file_name"],
        "page": meta["page"],
        "chunk_index": meta["chunk_index"],
        "flagged": bool(meta.get("flagged")),
        "flags": [f for f in (meta.get("flags") or "").split("; ") if f],
        **extra,
    }


def vector_search(query: str, k: int, document_ids=None) -> list[dict]:
    collection = _collection()
    if collection.count() == 0:
        return []
    result = collection.query(
        query_embeddings=models.embed([query]),
        n_results=min(k, collection.count()),
        where=_where(document_ids),
        include=["documents", "metadatas", "distances"],
    )
    return [
        _to_chunk(cid, text, meta, vector_score=1 - dist)
        for cid, text, meta, dist in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def all_chunks(document_ids=None) -> list[dict]:
    collection = _collection()
    if collection.count() == 0:
        return []
    result = collection.get(where=_where(document_ids), include=["documents", "metadatas"])
    chunks = [_to_chunk(cid, text, meta) for cid, text, meta in zip(result["ids"], result["documents"], result["metadatas"])]
    chunks.sort(key=lambda c: (c["document_id"], c["chunk_index"]))
    return chunks
