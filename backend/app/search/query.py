"""Search query logic with result grouping."""

from __future__ import annotations

from ..models.schemas import SearchResult, SearchResponse
from .vector_store import search as vector_search


def search_knowledge_base(
    query: str,
    limit: int = 10,
    source: str | None = None,
    category: str | None = None,
) -> SearchResponse:
    """Search the knowledge base and return grouped, ranked results.

    Groups consecutive chunks from the same document to provide
    more context in results.
    """
    # Fetch more results than requested to allow for grouping
    raw_results = vector_search(
        query=query,
        limit=limit * 2,  # Fetch extra for grouping
        source=source,
        category=category,
    )

    # Group consecutive chunks from the same document
    grouped = _group_consecutive_chunks(raw_results)

    # Trim to requested limit
    results = grouped[:limit]

    return SearchResponse(
        query=query,
        results=[
            SearchResult(
                text=r["text"],
                score=r["score"],
                source=r["source"],
                title=r["title"],
                categories=r["categories"],
                canonical_url=r.get("canonical_url"),
                chunk_index=r.get("chunk_index", 0),
                total_chunks=r.get("total_chunks", 1),
            )
            for r in results
        ],
        total=len(results),
    )


def _group_consecutive_chunks(results: list[dict]) -> list[dict]:
    """Group consecutive chunks from the same document.

    If chunk 2 and chunk 3 of the same document both appear in results,
    combine their text and use the higher score.
    """
    if not results:
        return []

    grouped = []
    seen_keys = set()

    for result in results:
        # Create a document key (source + title)
        doc_key = f"{result['source']}::{result['title']}"

        if doc_key in seen_keys:
            # Check if this is a consecutive chunk to an existing result
            for existing in grouped:
                existing_key = f"{existing['source']}::{existing['title']}"
                if existing_key == doc_key:
                    existing_idx = existing.get("chunk_index", 0)
                    new_idx = result.get("chunk_index", 0)
                    if abs(existing_idx - new_idx) == 1:
                        # Consecutive chunk: merge text
                        if new_idx > existing_idx:
                            existing["text"] = existing["text"] + "\n\n" + result["text"]
                        else:
                            existing["text"] = result["text"] + "\n\n" + existing["text"]
                        existing["score"] = max(existing["score"], result["score"])
                        break
            continue

        seen_keys.add(doc_key)
        grouped.append(result.copy())

    # Re-sort by score after grouping
    grouped.sort(key=lambda x: x["score"], reverse=True)

    return grouped
