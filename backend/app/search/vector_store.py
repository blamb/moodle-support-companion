"""ChromaDB vector store wrapper."""

from __future__ import annotations

import logging

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from ..config import CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL
from ..models.schemas import Chunk

logger = logging.getLogger(__name__)

# Module-level client and collection
_client = None
_collection = None


def get_collection():
    """Get or create the ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection '{COLLECTION_NAME}' ready "
            f"({_collection.count()} existing documents)"
        )
    return _collection


def reset_collection():
    """Delete and recreate the collection (for full re-ingestion)."""
    global _client, _collection
    if _client is None:
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

    try:
        _client.delete_collection(COLLECTION_NAME)
        logger.info(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass  # Collection didn't exist

    _collection = None
    return get_collection()


def add_chunks(chunks: list[Chunk], batch_size: int = 500):
    """Add chunks to the vector store.

    ChromaDB handles embedding via the configured embedding function.
    """
    collection = get_collection()

    # Process in batches
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        ids = [c.id for c in batch]
        documents = [c.text for c in batch]
        metadatas = [
            {
                "source": c.source,
                "title": c.title,
                "slug": c.slug or "",
                "canonical_url": c.canonical_url or "",
                "categories": c.categories or "",
                "chunk_index": c.chunk_index,
                "total_chunks": c.total_chunks,
                "author": c.author or "",
                "date_modified": c.date_modified or "",
            }
            for c in batch
        ]

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info(f"Upserted batch {i // batch_size + 1} ({len(batch)} chunks)")

    logger.info(f"Total chunks in store: {collection.count()}")


def search(
    query: str,
    limit: int = 10,
    source: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Search the vector store.

    Returns a list of dicts with 'text', 'score', and metadata fields.
    """
    collection = get_collection()

    # Build filter
    where_filter = _build_filter(source, category)

    results = collection.query(
        query_texts=[query],
        n_results=limit,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    # Format results
    output = []
    if results and results["documents"] and results["documents"][0]:
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc_text, meta, distance in zip(docs, metas, distances):
            # ChromaDB returns cosine distance; convert to similarity
            similarity = 1 - distance

            output.append({
                "text": doc_text,
                "score": round(similarity, 4),
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "categories": [
                    c.strip()
                    for c in meta.get("categories", "").split(",")
                    if c.strip()
                ],
                "canonical_url": meta.get("canonical_url") or None,
                "chunk_index": meta.get("chunk_index", 0),
                "total_chunks": meta.get("total_chunks", 1),
            })

    return output


def get_source_stats() -> list[dict]:
    """Get document and chunk counts per source."""
    collection = get_collection()
    total = collection.count()

    if total == 0:
        return []

    # Query for each known source
    sources = ["moodle_docs", "olproduction", "trubox", "tru_faq"]
    stats = []

    for source_name in sources:
        try:
            result = collection.get(
                where={"source": source_name},
                include=[],
                limit=1,
            )
            # Get count by querying with the source filter
            count_result = collection.count()  # ChromaDB doesn't have filtered count easily
            # Use get with a large limit to count
            all_ids = collection.get(
                where={"source": source_name},
                include=["metadatas"],
            )
            chunk_count = len(all_ids["ids"])

            if chunk_count > 0:
                # Count unique titles as proxy for document count
                titles = set()
                for meta in all_ids["metadatas"]:
                    titles.add(meta.get("title", ""))
                stats.append({
                    "source": source_name,
                    "document_count": len(titles),
                    "chunk_count": chunk_count,
                })
        except Exception as e:
            logger.warning(f"Error getting stats for {source_name}: {e}")

    return stats


def _build_filter(
    source: str | None = None,
    category: str | None = None,
) -> dict | None:
    """Build a ChromaDB where filter from optional parameters."""
    conditions = []

    if source:
        conditions.append({"source": {"$eq": source}})
    if category:
        conditions.append({"categories": {"$contains": category}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
