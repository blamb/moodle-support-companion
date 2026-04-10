"""Conversation service — orchestrates diagnostic sessions with Claude API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional, Dict, List

import anthropic

from ..config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, MAX_CONTEXT_CHUNKS
from ..search.query import search_knowledge_base
from ..cases.database import search_cases as search_past_cases, init_database
from .moodle_url import parse_urls_from_text, format_url_context_for_llm
from .prompts import build_system_prompt
from .templates import get_template_for_message

logger = logging.getLogger(__name__)

# In-memory session storage
_sessions: Dict[str, ConversationSession] = {}

# Shared conversation links: share_id -> session_id
_shared_links: Dict[str, str] = {}

# Session expiry: 2 hours
SESSION_TTL = 7200


class ConversationMessage:
    """A single message in a conversation."""

    def __init__(self, role: str, content: str, metadata: Optional[dict] = None):
        self.role = role  # "user" or "assistant"
        self.content = content
        self.timestamp = time.time()
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class ConversationSession:
    """A diagnostic conversation session."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.messages: List[ConversationMessage] = []
        self.mbz_context: str = ""
        self.images: Dict[str, dict] = {}  # message_index -> {"media_type": ..., "data": base64}
        self.created_at = time.time()
        self.updated_at = time.time()

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None):
        self.messages.append(ConversationMessage(role, content, metadata))
        self.updated_at = time.time()

    def add_image(self, media_type: str, base64_data: str):
        """Store an image to be included with the next user message."""
        idx = str(len(self.messages))  # Will be attached to the next message
        self.images[idx] = {"media_type": media_type, "data": base64_data}

    def get_claude_messages(self) -> list:
        """Convert message history to Claude API format."""
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "has_mbz_context": bool(self.mbz_context),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def create_session() -> ConversationSession:
    """Create a new diagnostic conversation session."""
    _cleanup_expired_sessions()
    session = ConversationSession()
    _sessions[session.id] = session
    logger.info(f"Created session {session.id}")
    return session


def get_session(session_id: str) -> Optional[ConversationSession]:
    """Get a session by ID."""
    session = _sessions.get(session_id)
    if session and (time.time() - session.updated_at) > SESSION_TTL:
        del _sessions[session_id]
        return None
    return session


def set_mbz_context(session_id: str, context: str):
    """Set .mbz course context for a session."""
    session = get_session(session_id)
    if session:
        session.mbz_context = context
        session.updated_at = time.time()


def create_share_link(session_id: str) -> Optional[str]:
    """Create a shareable link ID for a session."""
    session = get_session(session_id)
    if not session:
        return None
    # Check if already shared
    for share_id, sid in _shared_links.items():
        if sid == session_id:
            return share_id
    share_id = str(uuid.uuid4())[:8]
    _shared_links[share_id] = session_id
    return share_id


def get_session_by_share_id(share_id: str) -> Optional[ConversationSession]:
    """Get a session via its share ID."""
    session_id = _shared_links.get(share_id)
    if not session_id:
        return None
    return get_session(session_id)


async def send_message(
    session_id: str, user_message: str
) -> AsyncGenerator[str, None]:
    """Process a user message and stream the assistant response.

    Yields SSE-formatted events:
    - event: token\ndata: {text}\n\n
    - event: sources\ndata: {json}\n\n
    - event: url_context\ndata: {json}\n\n
    - event: done\ndata: {json}\n\n
    """
    session = get_session(session_id)
    if not session:
        yield _sse_event("error", {"message": "Session not found or expired"})
        return

    # 1. Parse Moodle URLs from the message
    url_contexts = parse_urls_from_text(user_message)
    if url_contexts:
        url_data = [ctx.to_dict() for ctx in url_contexts]
        yield _sse_event("url_context", url_data)

    # 2. Search knowledge base for relevant documentation
    kb_results = []
    try:
        search_response = search_knowledge_base(
            query=user_message, limit=MAX_CONTEXT_CHUNKS
        )
        kb_results = [
            {
                "title": r.title,
                "source": r.source,
                "text": r.text[:500],  # Truncate for SSE
                "score": r.score,
                "canonical_url": r.canonical_url,
            }
            for r in search_response.results
            if r.score > 0.35  # Only include reasonably relevant results
        ]
        if kb_results:
            yield _sse_event("sources", kb_results)
    except Exception as e:
        logger.warning(f"KB search failed: {e}")

    # 2b. Search past cases for similar issues
    past_cases = []
    try:
        init_database()
        past_cases = search_past_cases(user_message, limit=3)
    except Exception as e:
        logger.debug(f"Case search failed (may be empty): {e}")

    # 2c. Detect diagnostic template
    template = get_template_for_message(user_message)

    # 3. Build the augmented user message with context
    augmented_message = _build_augmented_message(
        user_message, url_contexts, kb_results, past_cases, template
    )

    # 4. Add user message to session history
    session.add_message("user", user_message, {
        "url_contexts": [ctx.to_dict() for ctx in url_contexts] if url_contexts else [],
        "kb_sources": [{"title": r["title"], "source": r["source"]} for r in kb_results],
    })

    # 5. Build Claude API messages
    system_prompt = build_system_prompt(session.mbz_context)

    # Use augmented message for the current turn, plain history for previous turns
    messages = []
    for i, msg in enumerate(session.messages[:-1]):  # All previous messages
        # Check if this message had an image attachment
        img = session.images.get(str(i))
        if img and msg.role == "user":
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]}},
                    {"type": "text", "text": msg.content},
                ],
            })
        else:
            messages.append({"role": msg.role, "content": msg.content})

    # Current user message with context injection — may include images
    current_msg_idx = str(len(session.messages) - 1)
    current_image = session.images.get(current_msg_idx)
    if current_image:
        messages.append({
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": current_image["media_type"], "data": current_image["data"]}},
                {"type": "text", "text": augmented_message},
            ],
        })
    else:
        messages.append({"role": "user", "content": augmented_message})

    # 6. Stream response from Claude
    full_response = ""
    try:
        client = anthropic.AsyncAnthropic()

        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield _sse_event("token", {"text": text})

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        yield _sse_event("error", {"message": f"API error: {str(e)}"})
        return
    except Exception as e:
        logger.error(f"Unexpected error in conversation: {e}")
        yield _sse_event("error", {"message": f"Error: {str(e)}"})
        return

    # 7. Detect mode from response
    mode = _detect_mode(full_response)

    # 8. Save assistant response to session
    session.add_message("assistant", full_response, {"mode": mode})

    # 9. Send completion event
    yield _sse_event("done", {
        "mode": mode,
        "full_response": full_response,
    })


def _build_augmented_message(
    user_message: str,
    url_contexts: list,
    kb_results: list,
    past_cases: list = None,
    template=None,
) -> str:
    """Build the user message with injected context for Claude."""
    parts = []

    # Diagnostic template (if detected)
    if template:
        parts.append(template.to_prompt_text())

    # URL context
    url_text = format_url_context_for_llm(url_contexts)
    if url_text:
        parts.append(url_text)

    # Past similar cases
    if past_cases:
        parts.append("## Similar Past Cases")
        parts.append("The team has handled similar issues before:\n")
        for case in past_cases[:3]:
            parts.append(f"### Case: {case.get('summary', 'Untitled')}")
            if case.get("diagnosis"):
                parts.append(f"**Diagnosis**: {case['diagnosis'][:300]}")
            if case.get("resolution"):
                parts.append(f"**Resolution**: {case['resolution'][:300]}")
            if case.get("tags"):
                tags = case["tags"] if isinstance(case["tags"], list) else [case["tags"]]
                parts.append(f"Tags: {', '.join(tags)}")
            parts.append("")

    # Knowledge base context
    if kb_results:
        parts.append("## Relevant Documentation")
        parts.append("The following documentation may be relevant:\n")
        for r in kb_results:
            parts.append(f"### {r['title']} ({r['source']})")
            parts.append(r["text"])
            if r.get("canonical_url"):
                parts.append(f"Source: {r['canonical_url']}")
            parts.append("")

    # The actual user message
    if parts:
        parts.append("---")
        parts.append("## User's message")

    parts.append(user_message)

    return "\n\n".join(parts)


def _detect_mode(response: str) -> str:
    """Detect the conversation mode from the response content."""
    response_lower = response.lower()

    # Check for RESOLVE indicators
    resolve_indicators = [
        "step-by-step",
        "here's the fix",
        "here is the fix",
        "to fix this",
        "recommended fix",
        "to resolve this",
        "draft message",
        "you can send",
        "communicate to",
        "tell the user",
        "reply to the user",
    ]
    if any(indicator in response_lower for indicator in resolve_indicators):
        return "resolve"

    # Check for EXPLORE indicators (questions)
    explore_indicators = [
        "🔧",
        "💬",
        "for you:",
        "ask the user:",
        "could you check",
        "can you verify",
        "please check",
        "could you look at",
        "let me ask",
        "before we diagnose",
        "before diagnosing",
        "i need to understand",
        "a few questions",
    ]
    if any(indicator in response_lower for indicator in explore_indicators):
        return "explore"

    # Check for DIAGNOSE indicators
    diagnose_indicators = [
        "likely cause",
        "probable cause",
        "most likely",
        "possible causes",
        "here's what's happening",
        "the issue is",
        "this is caused by",
        "this happens because",
        "this is likely",
        "based on what you've described",
    ]
    if any(indicator in response_lower for indicator in diagnose_indicators):
        return "diagnose"

    # Default to explore for early conversation, diagnose for later
    return "explore"


def _sse_event(event_type: str, data) -> str:
    """Format an SSE event string."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _cleanup_expired_sessions():
    """Remove sessions older than TTL."""
    now = time.time()
    expired = [
        sid for sid, session in _sessions.items()
        if (now - session.updated_at) > SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")
