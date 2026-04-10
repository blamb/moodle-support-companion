"""Text chunking for vector search indexing."""

import logging
import re

from ..config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE, SINGLE_CHUNK_THRESHOLD
from ..models.schemas import Document, Chunk

logger = logging.getLogger(__name__)


def chunk_document(doc: Document) -> list[Chunk]:
    """Split a document into chunks suitable for embedding.

    Short documents stay as single chunks. Longer documents are split
    at paragraph boundaries with overlap for context preservation.
    """
    text = doc.text.strip()
    if not text:
        return []

    # Short documents: keep as single chunk
    if len(text) <= SINGLE_CHUNK_THRESHOLD:
        return [_make_chunk(doc, text, 0, 1)]

    # Split into chunks
    texts = _recursive_split(text, CHUNK_SIZE, CHUNK_OVERLAP)

    # Filter out tiny chunks
    texts = [t for t in texts if len(t.strip()) >= MIN_CHUNK_SIZE]

    if not texts:
        return [_make_chunk(doc, text, 0, 1)]

    total = len(texts)
    return [_make_chunk(doc, t, i, total) for i, t in enumerate(texts)]


def _make_chunk(doc: Document, text: str, index: int, total: int) -> Chunk:
    """Create a Chunk from a Document and text fragment."""
    # Use file_hash for uniqueness (multiple docs can share a slug)
    unique_key = doc.file_hash or doc.slug or "unknown"
    chunk_id = f"{doc.source}::{unique_key}::chunk_{index}"

    return Chunk(
        id=chunk_id,
        text=text.strip(),
        source=doc.source,
        title=doc.title,
        slug=doc.slug,
        canonical_url=doc.canonical_url,
        categories=", ".join(doc.categories) if doc.categories else "",
        chunk_index=index,
        total_chunks=total,
        author=doc.author,
        date_modified=doc.date_modified,
    )


def _recursive_split(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Split text recursively using a hierarchy of separators.

    Tries to split at paragraph boundaries first, then lines,
    then sentences, then words.
    """
    separators = ["\n\n", "\n", ". ", " "]

    # If text fits in one chunk, return it
    if len(text) <= chunk_size:
        return [text]

    # Find the best separator that produces reasonable splits
    for sep in separators:
        parts = text.split(sep)
        if len(parts) > 1:
            return _merge_splits(parts, sep, chunk_size, overlap)

    # Last resort: hard split by character (shouldn't happen with space separator)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _merge_splits(
    parts: list[str],
    separator: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Merge split parts back into chunks of appropriate size with overlap."""
    chunks = []
    current_parts: list[str] = []
    current_len = 0

    for part in parts:
        part_len = len(part) + len(separator)

        if current_len + part_len > chunk_size and current_parts:
            # Save current chunk
            chunk_text = separator.join(current_parts)
            chunks.append(chunk_text)

            # Calculate overlap: keep trailing parts that fit in overlap window
            overlap_parts: list[str] = []
            overlap_len = 0
            for p in reversed(current_parts):
                if overlap_len + len(p) + len(separator) > overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p) + len(separator)

            current_parts = overlap_parts
            current_len = overlap_len

        current_parts.append(part)
        current_len += part_len

    # Don't forget the last chunk
    if current_parts:
        chunk_text = separator.join(current_parts)
        chunks.append(chunk_text)

    return chunks


def chunk_documents(documents: list[Document]) -> list[Chunk]:
    """Chunk a list of documents."""
    all_chunks = []
    for doc in documents:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)

    logger.info(
        f"Chunked {len(documents)} documents into {len(all_chunks)} chunks"
    )
    return all_chunks
