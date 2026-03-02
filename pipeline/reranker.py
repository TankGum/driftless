"""Cross-encoder reranker — runs via fastembed ONNX, zero API cost, no PyTorch needed.

Uses Xenova/ms-marco-MiniLM-L-6-v2 (ONNX conversion of ms-marco-MiniLM-L-6-v2).
"""
from __future__ import annotations

_model = None
_MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"


def get_reranker():
    global _model
    if _model is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        print(f"  [Reranker] Loading {_MODEL_NAME} (first time)...")
        _model = TextCrossEncoder(_MODEL_NAME)
    return _model


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank chunks by relevance to query using cross-encoder.

    Each returned chunk gets a 'rerank_score' key (float).
    Returns top_k chunks sorted descending by score.
    """
    if not chunks:
        return []

    model = get_reranker()
    documents = [c.get("content", "")[:1000] for c in chunks]
    scores = list(model.rerank(query, documents))

    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [{**chunk, "rerank_score": float(score)} for chunk, score in ranked[:top_k]]
