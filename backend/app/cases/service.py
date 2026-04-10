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

    return database.save_case(
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
