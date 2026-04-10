"""Search API endpoint."""

from typing import Optional

from fastapi import APIRouter, Query

from ..config import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT
from ..models.schemas import SearchResponse
from ..search.query import search_knowledge_base

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query", min_length=1),
    source: Optional[str] = Query(None, description="Filter by source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(
        DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description="Number of results",
    ),
):
    """Search the Moodle knowledge base.

    Returns semantically relevant document chunks ranked by similarity.
    """
    return search_knowledge_base(
        query=q,
        limit=limit,
        source=source,
        category=category,
    )
