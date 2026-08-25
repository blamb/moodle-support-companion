"""Ingestion trigger API.

Ingestion re-embeds every knowledge source, which is CPU-heavy and takes several
minutes. Running it inline in the request handler blocks the event loop and trips
the platform's request timeout — so instead we launch it in a worker thread and
return immediately. Progress and the final result are exposed via
``GET /ingest/status``.
"""

import asyncio
import logging
import time

from fastapi import APIRouter

from ..ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()

# State of the most recent (or in-progress) ingestion run.
_state: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "result": None,   # stats dict from run_ingestion() on success
    "error": None,    # error message on failure
}


def _run_job() -> None:
    """Run the pipeline in a worker thread and record the outcome."""
    try:
        _state["result"] = run_ingestion()
        _state["error"] = None
    except Exception as e:  # noqa: BLE001 — surface any failure via /ingest/status
        logger.exception("Ingestion failed")
        _state["error"] = str(e)
    finally:
        _state["running"] = False
        _state["finished_at"] = time.time()


@router.post("/ingest")
async def trigger_ingestion():
    """Start a full re-ingestion in the background and return immediately.

    The web server stays responsive while embedding runs in a worker thread.
    Poll ``GET /ingest/status`` for progress and the final stats.
    """
    if _state["running"]:
        return {"status": "already_running", "started_at": _state["started_at"]}

    _state.update(
        running=True,
        started_at=time.time(),
        finished_at=None,
        result=None,
        error=None,
    )
    # Fire-and-forget on the default thread pool; do NOT await it.
    asyncio.get_running_loop().run_in_executor(None, _run_job)
    logger.info("Ingestion started in background")
    return {"status": "started"}


@router.get("/ingest/status")
async def ingestion_status():
    """Report the state of the most recent (or in-progress) ingestion run."""
    return _state
