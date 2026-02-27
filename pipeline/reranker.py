"""Cross-encoder reranker — runs locally, zero API cost.

Uses cross-encoder/ms-marco-MiniLM-L-6-v2 from sentence-transformers.
Cross-encoder reads query + chunk together → better contextual understanding
than bi-encoder cosine similarity.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

_model: "CrossEncoder | None" = None
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def get_reranker() -> "CrossEncoder":
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        print(f"  [Reranker] Loading {_MODEL_NAME} (first time)...")
        _model = CrossEncoder(_MODEL_NAME)
    return _model


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank chunks by relevance to query using cross-encoder.

    Each returned chunk gets a 'rerank_score' key (float).
    Returns top_k chunks sorted descending by score.
    """
    if not chunks:
        return []

    model = get_reranker()
    pairs = [(query, c.get("content", "")[:1000]) for c in chunks]
    scores = model.predict(pairs)

    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    result = []
    for chunk, score in ranked[:top_k]:
        result.append({**chunk, "rerank_score": float(score)})
    return result
