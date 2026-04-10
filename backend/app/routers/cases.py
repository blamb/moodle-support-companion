"""Cases API endpoints — save, search, and manage diagnostic cases."""

from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..cases import service as case_service
from ..conversation.service import get_session

logger_name = __name__
router = APIRouter()


class SaveCaseRequest(BaseModel):
    session_id: str
    summary: str
    tags: Optional[List[str]] = None
    difficulty: int = 0


class SaveCaseResponse(BaseModel):
    case_id: str


class UpdateCaseRequest(BaseModel):
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[int] = None
    status: Optional[str] = None
    diagnosis: Optional[str] = None
    resolution: Optional[str] = None


@router.post("/cases", response_model=SaveCaseResponse)
async def save_case(request: SaveCaseRequest):
    """Save a conversation session as a tracked case."""
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    case_id = case_service.save_session_as_case(
        session_dict=session.to_dict(),
        summary=request.summary,
        tags=request.tags,
        difficulty=request.difficulty,
    )
    return SaveCaseResponse(case_id=case_id)


@router.get("/cases")
async def list_or_search_cases(
    q: Optional[str] = Query(None, description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all cases or search by query."""
    if q:
        cases = case_service.search_cases(q, limit)
    else:
        cases = case_service.list_cases(limit, offset)

    return {"cases": cases, "total": len(cases)}


@router.get("/cases/analytics")
async def get_analytics():
    """Get aggregate analytics across all cases."""
    return case_service.get_analytics()


@router.get("/cases/tags")
async def get_all_tags():
    """Get all unique tags used across cases."""
    return {"tags": case_service.list_all_tags()}


@router.get("/cases/export/csv")
async def export_csv():
    """Export all cases as a CSV file."""
    csv_content = case_service.export_cases_csv()
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="moodle-support-cases.csv"',
        },
    )


@router.get("/cases/by-tag/{tag}")
async def list_cases_by_tag(
    tag: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List cases filtered by a specific tag."""
    cases = case_service.list_cases_by_tag(tag, limit, offset)
    return {"cases": cases, "total": len(cases), "tag": tag}


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get a single case by ID."""
    case = case_service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, request: UpdateCaseRequest):
    """Update a case's metadata."""
    updates = {k: v for k, v in request.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    success = case_service.update_case(case_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Case not found")

    return {"status": "updated"}
