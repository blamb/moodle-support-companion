"""Sources API endpoint — stats and browsing."""

from fastapi import APIRouter

from ..models.schemas import SourcesResponse, SourceStats
from ..search.vector_store import get_source_stats, get_collection

router = APIRouter()


@router.get("/sources", response_model=SourcesResponse)
async def list_sources():
    """Get statistics for all ingested knowledge sources."""
    stats = get_source_stats()
    total_chunks = sum(s["chunk_count"] for s in stats)

    return SourcesResponse(
        sources=[
            SourceStats(
                source=s["source"],
                document_count=s["document_count"],
                chunk_count=s["chunk_count"],
            )
            for s in stats
        ],
        total_chunks=total_chunks,
    )
