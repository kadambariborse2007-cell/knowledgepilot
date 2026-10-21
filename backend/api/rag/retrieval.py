"""Hybrid retrieval: BM25 (keyword) + vector (semantic), fused with RRF, then reranked."""
import re
import threading

from rank_bm25 import BM25Okapi

from . import models, store

VECTOR_K = 20
BM25_K = 20
RERANK_CANDIDATES = 20
RRF_K = 60

STOPWORDS = set(
    "a an the and or of to in on for with is are was were be been by at from as that this it its "
    "what which who whom how why when where do does did can could should would will about into".split()
)

_bm25_lock = threading.Lock()
_bm25_cache = {"version": -1, "chunks": [], "index": None}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


def _bm25():
    with _bm25_lock:
        if _bm25_cache["version"] != store.version() or _bm25_cache["index"] is None:
            chunks = store.all_chunks()
            _bm25_cache["chunks"] = chunks
            _bm25_cache["index"] = BM25Okapi([tokenize(c["text"]) or ["_"] for c in chunks]) if chunks else None
            _bm25_cache["version"] = store.version()
        return _bm25_cache["chunks"], _bm25_cache["index"]


def bm25_search(query: str, k: int, document_ids=None) -> list[dict]:
    chunks, index = _bm25()
    if index is None:
        return []
    scores = index.get_scores(tokenize(query))
    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    results = []
    for i in ranked:
        if scores[i] <= 0:
            break
        if document_ids and chunks[i]["document_id"] not in document_ids:
            continue
        results.append({**chunks[i], "bm25_score": float(scores[i])})
        if len(results) >= k:
            break
    return results


def hybrid_search(query: str, top_k: int = 5, document_ids=None) -> list[dict]:
    """Return the top_k chunks (flagged ones included, marked with "flagged": True)."""
    vector_hits = store.vector_search(query, VECTOR_K, document_ids)
    keyword_hits = bm25_search(query, BM25_K, document_ids)

    fused = {}
    for hits in (vector_hits, keyword_hits):
        for rank, chunk in enumerate(hits):
            entry = fused.setdefault(chunk["id"], {**chunk, "rrf_score": 0.0})
            entry.update({k: v for k, v in chunk.items() if k.endswith("_score")})
            entry["rrf_score"] += 1.0 / (RRF_K + rank + 1)

    candidates = sorted(fused.values(), key=lambda c: c["rrf_score"], reverse=True)[:RERANK_CANDIDATES]
    scores = models.rerank(query, [c["text"] for c in candidates])
    for chunk, score in zip(candidates, scores):
        chunk["rerank_score"] = score
    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates[:top_k]
