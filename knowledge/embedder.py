from fastembed import TextEmbedding

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        print("  [Embedder] Đang tải model multilingual-e5-large lần đầu...")
        _model = TextEmbedding("intfloat/multilingual-e5-large")
    return _model


def embed_documents_batch(texts: list[str]) -> list[list[float]]:
    """Embed nhiều chunks — chạy local, không cần API key."""
    model = _get_model()
    return [emb.tolist() for emb in model.embed([t[:8192] for t in texts])]


def embed_query(text: str) -> list[float]:
    """Embedding cho câu hỏi của user khi search."""
    return next(_get_model().query_embed([text])).tolist()
