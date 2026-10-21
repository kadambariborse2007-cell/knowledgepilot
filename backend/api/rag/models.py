"""Local ONNX models (no PyTorch, no paid API).

- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Reranker:   cross-encoder ms-marco-MiniLM-L-6-v2
Both run on CPU through fastembed/onnxruntime so they fit in a 512 MB server.
"""
import threading

from django.conf import settings

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"

_lock = threading.Lock()
_embedder = None
_reranker = None


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            _embedder = TextEmbedding(EMBEDDING_MODEL, cache_dir=str(settings.MODEL_CACHE_DIR), threads=1)
    return _embedder


def get_reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            _reranker = TextCrossEncoder(RERANKER_MODEL, cache_dir=str(settings.MODEL_CACHE_DIR), threads=1)
    return _reranker


def embed(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in get_embedder().embed(texts, batch_size=32)]


def rerank(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    return [float(score) for score in get_reranker().rerank(query, texts, batch_size=16)]
