"""Embedding wrapper using sentence-transformers."""

import logging

from ..config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Lazy-loaded model instance
_model = None


def get_model():
    """Load the embedding model (lazy, loads once)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded")
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed a list of texts using the sentence-transformers model.

    Returns a list of embedding vectors (list of floats).
    """
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        convert_to_numpy=True,
    )
    return embeddings.tolist()
