"""Conversation API endpoints — diagnostic session management with SSE streaming."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel

from ..conversation.service import (
    create_session,
    get_session,
    send_message,
    set_mbz_context,
)
from ..conversation.mbz_parser import parse_mbz_file
from ..conversation.health_checker import check_course_health, format_health_report
from ..conversation.html_page_parser import parse_moodle_html

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateSessionResponse(BaseModel):
    session_id: str


class SendMessageRequest(BaseModel):
    message: str


class DraftReplyRequest(BaseModel):
    audience: str = "instructor"  # "instructor", "student", or "admin"
    tone: str = "professional"  # "professional", "friendly", "brief"


@router.post("/conversation", response_model=CreateSessionResponse)
async def create_conversation():
    """Create a new diagnostic conversation session."""
    session = create_session()
    return CreateSessionResponse(session_id=session.id)


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """Get the full conversation history for a session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session.to_dict()


@router.post("/conversation/{session_id}/message")
async def send_conversation_message(session_id: str, request: SendMessageRequest):
    """Send a message and stream the assistant response via SSE.

    Returns a Server-Sent Events stream with these event types:
    - token: individual text tokens as they're generated
    - sources: knowledge base documents used as context
    - url_context: parsed Moodle URLs detected in the message
    - done: final event with complete response and detected mode
    - error: if something goes wrong
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return StreamingResponse(
        send_message(session_id, request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/conversation/{session_id}/mbz")
async def upload_mbz(session_id: str, file: UploadFile = File(...)):
    """Upload a .mbz course backup to add course context to the session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Validate file
    if not file.filename or not file.filename.endswith(".mbz"):
        raise HTTPException(status_code=400, detail="File must be a .mbz Moodle backup")

    # Check file size (max 500MB)
    content = await file.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 500MB)")

    # Save to temp file and parse
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".mbz", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        course_context = parse_mbz_file(tmp_path)

        # Run health checks
        health_issues = check_course_health(course_context)
        health_report = format_health_report(health_issues)

        # Set the context on the session (include health report)
        full_context = course_context.summary_text
        if health_issues:
            full_context += f"\n\n{health_report}"
        set_mbz_context(session_id, full_context)

        return {
            "status": "ok",
            "course": course_context.to_dict(),
            "health_issues": [i.to_dict() for i in health_issues],
            "health_report": health_report,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing .mbz upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse .mbz file")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/conversation/{session_id}/screenshot")
async def upload_screenshot(session_id: str, file: UploadFile = File(...)):
    """Upload a screenshot for the Companion to analyze visually.

    Supports PNG, JPG, GIF, and WebP. The image is stored in the session
    and included with the next message sent to Claude's vision API.
    """
    import base64

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Validate file type
    allowed_types = {
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/jpg": "jpeg",
        "image/gif": "gif",
        "image/webp": "webp",
    }

    content_type = file.content_type or ""
    if content_type not in allowed_types:
        # Try to detect from extension
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        ext_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
        content_type = ext_map.get(ext, "")
        if not content_type:
            raise HTTPException(status_code=400, detail="File must be an image (PNG, JPG, GIF, or WebP)")

    # Read and validate size (max 20MB — Claude's limit)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 20MB)")

    # Store as base64 in the session
    b64_data = base64.b64encode(content).decode("utf-8")
    session.add_image(content_type, b64_data)

    return {
        "status": "ok",
        "filename": file.filename,
        "size": len(content),
        "media_type": content_type,
        "message": "Screenshot attached. It will be included with your next message.",
    }


@router.post("/conversation/{session_id}/html")
async def upload_html_page(session_id: str, file: UploadFile = File(...)):
    """Upload a saved Moodle HTML page for context extraction.

    The technologist saves a Moodle page via Cmd+S / Ctrl+S in their browser,
    then uploads it here. The Companion extracts course structure, settings,
    gradebook data, errors, etc.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Validate file
    filename = file.filename or ""
    if not filename.endswith((".html", ".htm")):
        raise HTTPException(status_code=400, detail="File must be an HTML file (.html or .htm)")

    # Read content
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB max
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    try:
        html_text = content.decode("utf-8", errors="replace")
        page_context = parse_moodle_html(html_text)

        # Add the parsed context to the session's mbz_context (append to existing)
        existing = session.mbz_context
        separator = "\n\n---\n\n" if existing else ""
        session.mbz_context = existing + separator + page_context.summary_text
        session.updated_at = __import__("time").time()

        return {
            "status": "ok",
            "page": page_context.to_dict(),
        }

    except Exception as e:
        logger.error(f"Error parsing HTML page: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse HTML file")


@router.post("/conversation/{session_id}/draft-reply")
async def generate_draft_reply(session_id: str, request: DraftReplyRequest):
    """Generate a draft reply suitable for sending to the end user via TeamDynamix.

    Uses the conversation history to craft a professional response
    tailored to the audience (instructor, student, or admin).
    """
    import anthropic
    from ..config import CLAUDE_MODEL

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if not session.messages:
        raise HTTPException(status_code=400, detail="No conversation history to draft from")

    # Build a summary of the conversation for the draft prompt
    conversation_summary = []
    for msg in session.messages:
        role_label = "Support technologist" if msg.role == "user" else "Companion analysis"
        conversation_summary.append(f"**{role_label}**: {msg.content[:500]}")

    summary_text = "\n\n".join(conversation_summary)

    audience_guidance = {
        "instructor": "Write for a university instructor/faculty member. They understand course setup basics but may not know Moodle terminology deeply. Be respectful of their time.",
        "student": "Write for a university student. Use simple, non-technical language. Be encouraging and provide clear step-by-step instructions.",
        "admin": "Write for a university IT administrator. Use technical terminology freely. Be concise and focus on the specific configuration details.",
    }

    tone_guidance = {
        "professional": "Use a professional, helpful tone appropriate for university communication.",
        "friendly": "Use a warm, approachable tone while remaining professional.",
        "brief": "Keep it as concise as possible. Just the essential information and steps.",
    }

    draft_prompt = f"""Based on the following diagnostic conversation, draft a reply that can be sent to the end user via the university's ticketing system (TeamDynamix).

{audience_guidance.get(request.audience, audience_guidance['instructor'])}
{tone_guidance.get(request.tone, tone_guidance['professional'])}

The reply should:
1. Acknowledge their issue briefly
2. Explain what was found (in terms they'll understand)
3. Provide clear fix instructions or next steps
4. Offer to help further if needed

Do NOT include internal diagnostic notes or technical details the user doesn't need.
Do NOT mention the Companion tool, knowledge base, or internal processes.
Sign off as "Moodle Support — Learning Technology & Innovation, TRU"

## Diagnostic Conversation

{summary_text}

## Draft the reply now:"""

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": draft_prompt}],
        )
        draft_text = response.content[0].text

        return {
            "draft": draft_text,
            "audience": request.audience,
            "tone": request.tone,
        }

    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"API error: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating draft reply: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate draft")


@router.post("/conversation/{session_id}/share")
async def share_conversation(session_id: str):
    """Generate a shareable link for this conversation."""
    from ..conversation.service import create_share_link

    share_id = create_share_link(session_id)
    if not share_id:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return {"share_id": share_id}


@router.get("/shared/{share_id}")
async def get_shared_conversation(share_id: str):
    """View a shared conversation (read-only snapshot)."""
    from ..conversation.service import get_session_by_share_id

    session = get_session_by_share_id(share_id)
    if not session:
        raise HTTPException(status_code=404, detail="Shared conversation not found or expired")

    return session.to_dict()


@router.get("/conversation/{session_id}/export")
async def export_conversation(session_id: str):
    """Export the conversation as a markdown document.

    Suitable for attaching to TeamDynamix tickets, team documentation,
    or training materials.
    """
    import time as _time

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if not session.messages:
        raise HTTPException(status_code=400, detail="No conversation to export")

    lines = []
    lines.append("# Moodle Support Companion — Diagnostic Session")
    lines.append("")

    date_str = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(session.created_at))
    lines.append(f"**Date**: {date_str}")
    lines.append(f"**Session ID**: {session.id}")
    if session.mbz_context:
        # Extract course name from first line
        first_line = session.mbz_context.split("\n")[0]
        lines.append(f"**Course context**: {first_line}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in session.messages:
        mode = msg.metadata.get("mode", "")
        mode_label = f" [{mode.upper()}]" if mode else ""

        if msg.role == "user":
            lines.append(f"## Technologist{mode_label}")
        else:
            lines.append(f"## Companion{mode_label}")

        lines.append("")
        lines.append(msg.content)
        lines.append("")

        # Include sources if present
        kb_sources = msg.metadata.get("kb_sources", [])
        if kb_sources:
            lines.append("*Sources consulted:*")
            for src in kb_sources:
                lines.append(f"- {src.get('title', '')} ({src.get('source', '')})")
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("*Exported from Moodle Support Companion — TRU Learning Technology & Innovation*")

    markdown_content = "\n".join(lines)

    return PlainTextResponse(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="diagnostic-session-{session.id[:8]}.md"',
        },
    )
