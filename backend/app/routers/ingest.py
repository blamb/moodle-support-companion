"""Ingestion trigger API endpoint."""

import logging

from fastapi import APIRouter, BackgroundTasks

from ..models.schemas import IngestResponse
from ..ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()

# Track ingestion state
_ingestion_running = False


@router.post("/ingest", response_model=IngestResponse)
async def trigger_ingestion():
    """Trigger a full re-ingestion of all knowledge sources.

    This re-parses all documents, re-chunks, and re-embeds everything.
    It may take several minutes depending on the machine.
    """
    global _ingestion_running

    if _ingestion_running:
        return IngestResponse(
            status="already_running",
            sources_ingested=[],
            total_documents=0,
            total_chunks=0,
            duration_seconds=0,
        )

    _ingestion_running = True
    try:
        stats = run_ingestion()
        return IngestResponse(**stats)
    finally:
        _ingestion_running = False
