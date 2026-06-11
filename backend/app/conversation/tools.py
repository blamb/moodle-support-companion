"""Claude tool definitions and executors for the diagnostic conversation.

Instead of injecting a single up-front knowledge-base search into every
message, the model drives its own investigation: it can search the knowledge
base (and reformulate queries when results miss), look up similar past cases,
and pull the uploaded course context on demand.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from ..config import MAX_CONTEXT_CHUNKS
from ..search.query import search_knowledge_base
from ..cases.database import search_cases as search_past_cases, init_database

logger = logging.getLogger(__name__)

# Minimum relevance score for KB results returned to the model
KB_RELEVANCE_THRESHOLD = 0.25
# Cap per-result text returned to the model
KB_RESULT_MAX_CHARS = 2500
CASE_FIELD_MAX_CHARS = 800


TOOL_DEFINITIONS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search TRU's Moodle knowledge base (Moodle 4.5 documentation, TRU "
            "FAQs, and internal guides) using semantic search. Call this BEFORE "
            "diagnosing any issue that involves a specific Moodle feature, "
            "setting, or behavior — do not rely on general Moodle knowledge "
            "when documentation might exist. If the first search doesn't "
            "address the issue, reformulate the query (different terminology, "
            "the specific setting name, the module type) and search again."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query. Use Moodle terminology — e.g. "
                        "'gradebook aggregation weighted mean', "
                        "'activity completion conditions', "
                        "'assignment submission visibility'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_past_cases",
        "description": (
            "Search the team's resolved support cases for similar issues. Call "
            "this once near the start of investigating any new issue — a past "
            "case with a confirmed resolution is often the fastest path to a "
            "diagnosis. Results include the team's diagnosis and resolution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Keywords describing the issue, e.g. "
                        "'quiz grades missing gradebook'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_course_context",
        "description": (
            "Retrieve the course structure context uploaded for this session "
            "(parsed from a .mbz course backup or saved Moodle HTML pages): "
            "activities, gradebook setup, completion tracking, sections, and "
            "any automated health-check findings. Call this whenever the "
            "conversation indicates course context was uploaded and the issue "
            "relates to course configuration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_tool(
    name: str, tool_input: dict, session
) -> Tuple[str, List[dict], bool]:
    """Execute a tool call from Claude.

    Returns (result_text, kb_sources_for_frontend, is_error).
    kb_sources_for_frontend is non-empty only for knowledge-base searches.
    """
    try:
        if name == "search_knowledge_base":
            return _run_kb_search(tool_input.get("query", ""))
        if name == "search_past_cases":
            return _run_case_search(tool_input.get("query", "")), [], False
        if name == "get_course_context":
            return _get_course_context(session), [], False
        return f"Unknown tool: {name}", [], True
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return f"Tool error: {e}", [], True


def _run_kb_search(query: str) -> Tuple[str, List[dict], bool]:
    if not query.strip():
        return "Empty query — provide search terms.", [], True

    response = search_knowledge_base(query=query, limit=MAX_CONTEXT_CHUNKS)

    results = [r for r in response.results if r.score > KB_RELEVANCE_THRESHOLD]
    if not results:
        return (
            "No relevant documentation found for this query. Try different "
            "terminology, or note to the technologist that our docs don't "
            "cover this.",
            [],
            False,
        )

    parts = []
    sources = []
    for r in results:
        parts.append(f"### {r.title} ({r.source})")
        parts.append(r.text[:KB_RESULT_MAX_CHARS])
        if r.canonical_url:
            parts.append(f"Source: {r.canonical_url}")
        parts.append("")
        sources.append({
            "title": r.title,
            "source": r.source,
            "text": r.text[:500],
            "score": r.score,
            "canonical_url": r.canonical_url,
        })

    return "\n".join(parts), sources, False


def _run_case_search(query: str) -> str:
    if not query.strip():
        return "Empty query — provide search terms."

    init_database()
    cases = search_past_cases(query, limit=3)
    if not cases:
        return "No similar past cases found."

    parts = []
    for case in cases:
        parts.append(f"### Case: {case.get('summary', 'Untitled')}")
        if case.get("problem_description"):
            parts.append(
                f"**Problem**: {case['problem_description'][:CASE_FIELD_MAX_CHARS]}"
            )
        if case.get("diagnosis"):
            parts.append(f"**Diagnosis**: {case['diagnosis'][:CASE_FIELD_MAX_CHARS]}")
        if case.get("resolution"):
            parts.append(
                f"**Resolution**: {case['resolution'][:CASE_FIELD_MAX_CHARS]}"
            )
        tags = case.get("tags")
        if tags:
            tags = tags if isinstance(tags, list) else [tags]
            parts.append(f"Tags: {', '.join(tags)}")
        parts.append("")

    return "\n".join(parts)


def _get_course_context(session) -> str:
    if session is not None and session.mbz_context:
        return session.mbz_context
    return (
        "No course backup or saved page has been uploaded for this session. "
        "If course configuration details would help, suggest the technologist "
        "upload a .mbz backup or a saved Moodle HTML page."
    )
