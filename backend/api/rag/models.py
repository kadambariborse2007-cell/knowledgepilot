"""Local ONNX models (no PyTorch, no paid API).

- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Reranker:   cross-encoder ms-marco-MiniLM-L-6-v2
Both run on CPU through fastembed/onnxruntime, using the int8-quantized ONNX
files so they fit in a 512 MB server.
"""
import gc
import threading

from django.conf import settings

EMBEDDING_MODEL = "Xenova/all-MiniLM-L6-v2"
RERANKER_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2-quantized"
QUANTIZED_FILE = "onnx/model_quantized.onnx"

_lock = threading.Lock()
_embedder = None
_reranker = None
_registered = False


def _register():
    global _registered
    if _registered:
        return
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    TextEmbedding.add_custom_model(
        model=EMBEDDING_MODEL,
        pooling=PoolingType.MEAN,
        normalization=True,
        sources=ModelSource(hf="Xenova/all-MiniLM-L6-v2"),
        dim=384,
        model_file=QUANTIZED_FILE,
    )
    TextCrossEncoder.add_custom_model(
        model=RERANKER_MODEL,
        sources=ModelSource(hf="Xenova/ms-marco-MiniLM-L-6-v2"),
        model_file=QUANTIZED_FILE,
    )
    _registered = True


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            _register()

            _embedder = TextEmbedding(EMBEDDING_MODEL, cache_dir=str(settings.MODEL_CACHE_DIR), threads=1)
    return _embedder


def get_reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            _register()

            _reranker = TextCrossEncoder(RERANKER_MODEL, cache_dir=str(settings.MODEL_CACHE_DIR), threads=1)
    return _reranker


def embed(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in get_embedder().embed(texts, batch_size=32)]


def rerank(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    return [float(score) for score in get_reranker().rerank(query, texts, batch_size=16)]


def unload():
    """Free the models (they are reloaded on the next request)."""
    global _embedder, _reranker
    with _lock:
        _embedder = None
        _reranker = None
    gc.collect()
