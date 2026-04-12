"""Case tracking service — save and search diagnostic sessions."""

from __future__ import annotations

from typing import Optional, List, Dict

from . import database


def save_session_as_case(
    session_dict: dict,
    summary: str,
    tags: Optional[List[str]] = None,
    difficulty: int = 0,
) -> str:
    """Save a conversation session as a tracked case.

    Extracts problem description, diagnosis, and resolution
    from the conversation history.
    """
    messages = session_dict.get("messages", [])

    # Extract key parts from conversation
    problem_description = ""
    diagnosis = ""
    resolution = ""
    moodle_module = ""
    course_id = ""

    for msg in messages:
        if msg["role"] == "user" and not problem_description:
            problem_description = msg["content"][:1000]

        if msg["role"] == "assistant":
            mode = msg.get("metadata", {}).get("mode", "")
            if mode == "diagnose":
                diagnosis = msg["content"][:2000]
            elif mode == "resolve":
                resolution = msg["content"][:2000]

        # Extract module/course from URL contexts
        url_contexts = msg.get("metadata", {}).get("url_contexts", [])
        for ctx in url_contexts:
            if ctx.get("module_type") and not moodle_module:
                moodle_module = ctx["module_type"]
            if ctx.get("course_id") and not course_id:
                course_id = str(ctx["course_id"])

    # If no explicit diagnosis/resolution detected, use last assistant message
    if not diagnosis and not resolution:
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                diagnosis = msg["content"][:2000]
                break

    case_id = database.save_case(
        summary=summary,
        problem_description=problem_description,
        diagnosis=diagnosis,
        resolution=resolution,
        conversation=messages,
        tags=tags,
        difficulty=difficulty,
        moodle_module=moodle_module,
        course_id=course_id,
    )

    # Ingest the resolved case back into ChromaDB as a synthetic document
    # so future KB searches can find past resolutions
    _ingest_case_to_kb(
        case_id=case_id,
        summary=summary,
        problem_description=problem_description,
        diagnosis=diagnosis,
        resolution=resolution,
        tags=tags,
        moodle_module=moodle_module,
    )

    return case_id


def _ingest_case_to_kb(
    case_id: str,
    summary: str,
    problem_description: str,
    diagnosis: str,
    resolution: str,
    tags: Optional[List[str]] = None,
    moodle_module: str = "",
) -> None:
    """Ingest a resolved case into ChromaDB as a synthetic document.

    This makes past resolutions discoverable via knowledge base search,
    so future similar issues can benefit from the team's experience.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Build a synthetic document from the case
    parts = [f"Resolved Case: {summary}"]
    if problem_description:
        parts.append(f"Problem: {problem_description[:800]}")
    if diagnosis:
        parts.append(f"Diagnosis: {diagnosis[:800]}")
    if resolution:
        parts.append(f"Resolution: {resolution[:800]}")
    if moodle_module:
        parts.append(f"Moodle module: {moodle_module}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    synthetic_text = "\n\n".join(parts)

    try:
        from ..search.vector_store import get_collection

        collection = get_collection()
        collection.upsert(
            ids=[f"resolved_case::{case_id}"],
            documents=[synthetic_text],
            metadatas=[{
                "source": "resolved_cases",
                "title": f"Past Case: {summary[:100]}",
                "slug": case_id,
                "canonical_url": "",
                "categories": ", ".join(tags) if tags else "",
                "chunk_index": 0,
                "total_chunks": 1,
                "author": "LT&I Team",
                "date_modified": "",
            }],
        )
        logger.info(f"Ingested case {case_id} into knowledge base")
    except Exception as e:
        # Non-critical — case is still saved in SQLite
        logger.warning(f"Failed to ingest case into KB: {e}")


def search_cases(query: str, limit: int = 20) -> List[Dict]:
    """Search past cases."""
    return database.search_cases(query, limit)


def list_cases(limit: int = 50, offset: int = 0) -> List[Dict]:
    """List all cases."""
    return database.list_cases(limit, offset)


def get_case(case_id: str) -> Optional[Dict]:
    """Get a single case."""
    return database.get_case(case_id)


def update_case(case_id: str, **kwargs) -> bool:
    """Update a case."""
    return database.update_case(case_id, **kwargs)


def get_analytics() -> Dict:
    """Get case analytics."""
    return database.get_analytics()


def export_cases_csv() -> str:
    """Export all cases as CSV."""
    return database.export_cases_csv()


def list_all_tags() -> List[str]:
    """Get all unique tags."""
    return database.list_all_tags()


def list_cases_by_tag(tag: str, limit: int = 50, offset: int = 0) -> List[Dict]:
    """List cases with a specific tag."""
    return database.list_cases_by_tag(tag, limit, offset)
