"""Retrieval Guard — prevents hallucination by refusing low-confidence answers.

Layer L2 of the 5-layer anti-hallucination strategy.
If the top rerank score < RETRIEVAL_THRESHOLD, we return a fixed refusal
message instead of calling Claude for generation.
"""

RETRIEVAL_THRESHOLD = 0.3  # Tune after eval with RAGAS

NO_INFO_MESSAGE = (
    "Tôi không tìm thấy thông tin chắc chắn trong tài liệu hiện có. "
    "Vui lòng kiểm tra trực tiếp với bộ phận liên quan."
)


class NoRelevantDocError(Exception):
    """Raised when retrieved chunks are below confidence threshold."""
    pass


def retrieval_guard(chunks: list[dict]) -> list[dict]:
    """Check if top chunk passes the confidence threshold.

    Args:
        chunks: Reranked chunks with 'rerank_score' key.

    Returns:
        The same chunks list if guard passes.

    Raises:
        NoRelevantDocError: If no chunks or top score < RETRIEVAL_THRESHOLD.
    """
    if not chunks:
        raise NoRelevantDocError("No chunks retrieved")

    top_score = chunks[0].get("rerank_score", 0.0)
    if top_score < RETRIEVAL_THRESHOLD:
        raise NoRelevantDocError(
            f"Top rerank score {top_score:.3f} < threshold {RETRIEVAL_THRESHOLD}"
        )

    return chunks
