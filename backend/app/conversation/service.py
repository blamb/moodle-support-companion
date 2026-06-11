"""Conversation service — orchestrates diagnostic sessions with Claude API.

The model drives its own investigation via tools (knowledge-base search,
past-case search, course context) instead of receiving a single up-front
context injection. Sessions are persisted to SQLite so they survive restarts.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import AsyncGenerator, Optional, Dict, List

import anthropic

from ..config import (
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
)
from . import session_store
from .moodle_url import parse_urls_from_text, format_url_context_for_llm
from .prompts import SYSTEM_PROMPT
from .templates import get_template_for_message
from .tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

# In-memory session cache (backed by SQLite via session_store)
_sessions: Dict[str, ConversationSession] = {}


class ConversationMessage:
    """A single message in a conversation."""

    def __init__(self, role: str, content: str, metadata: Optional[dict] = None,
                 timestamp: Optional[float] = None):
        self.role = role  # "user" or "assistant"
        self.content = content
        self.timestamp = timestamp if timestamp is not None else time.time()
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
        self.updated_at = time.time()
        persist_session(self)

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

    def to_state_dict(self) -> dict:
        """Full state for persistence (includes context and images)."""
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "mbz_context": self.mbz_context,
            "images": self.images,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_state_dict(cls, state: dict) -> "ConversationSession":
        session = cls()
        session.id = state["id"]
        session.messages = [
            ConversationMessage(
                role=m["role"],
                content=m["content"],
                metadata=m.get("metadata") or {},
                timestamp=m.get("timestamp"),
            )
            for m in state.get("messages", [])
        ]
        session.mbz_context = state.get("mbz_context", "")
        session.images = state.get("images", {})
        session.created_at = state.get("created_at", time.time())
        session.updated_at = state.get("updated_at", time.time())
        return session


def persist_session(session: ConversationSession):
    """Write-through a session to the SQLite store."""
    session_store.save_session(
        session.id, session.to_state_dict(), session.created_at, session.updated_at
    )


def create_session() -> ConversationSession:
    """Create a new diagnostic conversation session."""
    session_store.cleanup_expired()
    session = ConversationSession()
    _sessions[session.id] = session
    persist_session(session)
    logger.info(f"Created session {session.id}")
    return session


def get_session(session_id: str) -> Optional[ConversationSession]:
    """Get a session by ID — from memory, falling back to the SQLite store."""
    session = _sessions.get(session_id)
    if session:
        return session

    state = session_store.load_session(session_id)
    if state:
        session = ConversationSession.from_state_dict(state)
        _sessions[session.id] = session
        return session
    return None


def set_mbz_context(session_id: str, context: str):
    """Set .mbz course context for a session."""
    session = get_session(session_id)
    if session:
        session.mbz_context = context
        session.updated_at = time.time()
        persist_session(session)


def append_page_context(session_id: str, context: str):
    """Append parsed page context (e.g. saved HTML) to a session."""
    session = get_session(session_id)
    if session:
        separator = "\n\n---\n\n" if session.mbz_context else ""
        session.mbz_context = session.mbz_context + separator + context
        session.updated_at = time.time()
        persist_session(session)


def create_share_link(session_id: str) -> Optional[str]:
    """Create a shareable link ID for a session."""
    session = get_session(session_id)
    if not session:
        return None
    existing = session_store.get_share_link_for_session(session_id)
    if existing:
        return existing
    share_id = str(uuid.uuid4())[:8]
    session_store.save_share_link(share_id, session_id)
    return share_id


def get_session_by_share_id(share_id: str) -> Optional[ConversationSession]:
    """Get a session via its share ID."""
    session_id = session_store.resolve_share_link(share_id)
    if not session_id:
        return None
    return get_session(session_id)


_MODE_RE = re.compile(
    r"^\s*MODE:\s*(explore|diagnose|resolve)\b[^\n]*\n?", re.IGNORECASE
)


class _ModeMarkerFilter:
    """Strips a leading 'MODE: <mode>' line from a streamed text sequence.

    The model is instructed to begin each response with a machine-readable
    mode declaration. This filter buffers just enough of the stream to detect
    and remove it, passing everything else through unchanged.
    """

    MAX_BUFFER = 32

    def __init__(self):
        self._buffer = ""
        self._active = True
        self.mode: Optional[str] = None

    def feed(self, text: str) -> str:
        if not self._active:
            return text
        self._buffer += text

        if "\n" in self._buffer:
            match = _MODE_RE.match(self._buffer)
            self._active = False
            out = self._buffer[match.end():] if match else self._buffer
            if match:
                self.mode = match.group(1).lower()
                out = out.lstrip("\n")
            self._buffer = ""
            return out

        # No newline yet — keep buffering only while this could still be a marker
        probe = self._buffer.lstrip().upper()
        could_be_marker = (
            "MODE:".startswith(probe) if len(probe) < 5 else probe.startswith("MODE:")
        )
        if not could_be_marker or len(self._buffer) > self.MAX_BUFFER:
            self._active = False
            out, self._buffer = self._buffer, ""
            return out
        return ""

    def flush(self) -> str:
        """Return any remaining buffered text at end of stream."""
        self._active = False
        if not self._buffer:
            return ""
        match = _MODE_RE.match(self._buffer + "\n")
        if match:
            self.mode = match.group(1).lower()
            self._buffer = ""
            return ""
        out, self._buffer = self._buffer, ""
        return out


async def send_message(
    session_id: str, user_message: str
) -> AsyncGenerator[str, None]:
    """Process a user message and stream the assistant response.

    Runs an agentic loop: Claude searches the knowledge base and past cases
    via tools as needed, then answers. Yields SSE-formatted events:
    - event: token\ndata: {text}\n\n
    - event: sources\ndata: {json}            (cumulative KB sources)
    - event: url_context\ndata: {json}
    - event: tool_activity\ndata: {json}      (informational; safe to ignore)
    - event: done\ndata: {json}
    - event: error\ndata: {json}
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

    # 2. Detect diagnostic template
    template = get_template_for_message(user_message)

    # 3. Build the augmented user message
    augmented_message = _build_augmented_message(
        user_message, url_contexts, template, bool(session.mbz_context)
    )

    # 4. Add user message to session history
    session.add_message("user", user_message, {
        "url_contexts": [ctx.to_dict() for ctx in url_contexts] if url_contexts else [],
    })
    persist_session(session)

    # 5. Build Claude API messages from history
    messages = _build_api_messages(session, augmented_message)

    # System prompt is static — mark it cacheable (covers tools + system prefix)
    system_blocks = [{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]

    # 6. Agentic loop: stream, execute tools, repeat until the model answers
    client = anthropic.AsyncAnthropic()
    response_parts: List[str] = []
    all_sources: List[dict] = []
    seen_source_keys = set()
    mode: Optional[str] = None
    stop_reason: Optional[str] = None

    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            # On the last allowed iteration, force a final answer (no tools)
            last_chance = iteration == MAX_TOOL_ITERATIONS - 1
            request_kwargs = dict(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=system_blocks,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
            if last_chance:
                request_kwargs["tool_choice"] = {"type": "none"}

            marker_filter = _ModeMarkerFilter()
            async with client.messages.stream(**request_kwargs) as stream:
                async for text in stream.text_stream:
                    out = marker_filter.feed(text)
                    if out:
                        response_parts.append(out)
                        yield _sse_event("token", {"text": out})
                remaining = marker_filter.flush()
                if remaining:
                    response_parts.append(remaining)
                    yield _sse_event("token", {"text": remaining})
                response = await stream.get_final_message()

            if marker_filter.mode:
                mode = marker_filter.mode
            stop_reason = response.stop_reason

            if stop_reason == "tool_use":
                # Echo the assistant turn (including tool_use blocks), execute
                # each tool, and feed results back
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    yield _sse_event("tool_activity", {
                        "tool": block.name,
                        "input": block.input,
                    })
                    result_text, sources, is_error = execute_tool(
                        block.name, block.input or {}, session
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                        "is_error": is_error,
                    })
                    new_sources = [
                        s for s in sources
                        if (s["title"], s["source"]) not in seen_source_keys
                    ]
                    if new_sources:
                        for s in new_sources:
                            seen_source_keys.add((s["title"], s["source"]))
                        all_sources.extend(new_sources)
                        yield _sse_event("sources", all_sources)
                if not tool_results:
                    break  # defensive: tool_use stop with no tool blocks
                messages.append({"role": "user", "content": tool_results})
                # Separate text written before tool calls from what follows
                if response_parts and response_parts[-1].strip():
                    response_parts.append("\n\n")
                    yield _sse_event("token", {"text": "\n\n"})
                continue

            if stop_reason == "pause_turn":
                # Server paused the turn — re-send to resume
                messages.append({"role": "assistant", "content": response.content})
                continue

            break  # end_turn, max_tokens, refusal, etc.

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        yield _sse_event("error", {"message": f"API error: {str(e)}"})
        return
    except Exception as e:
        logger.error(f"Unexpected error in conversation: {e}")
        yield _sse_event("error", {"message": f"Error: {str(e)}"})
        return

    full_response = "".join(response_parts).strip()

    # 7. Handle refusal — the model (or its safety layer) declined to answer
    if stop_reason == "refusal":
        yield _sse_event("error", {
            "message": "The model declined to respond to this request. "
                       "Try rephrasing the issue.",
        })
        if not full_response:
            return

    if not full_response:
        yield _sse_event("error", {"message": "The model returned an empty response."})
        return

    # 8. Determine mode: model-declared marker, falling back to heuristics
    if not mode:
        mode = _detect_mode(full_response)

    # 9. Save assistant response to session
    session.add_message("assistant", full_response, {
        "mode": mode,
        "kb_sources": [
            {"title": s["title"], "source": s["source"]} for s in all_sources
        ],
    })
    persist_session(session)

    # 10. Send completion event
    yield _sse_event("done", {
        "mode": mode,
        "full_response": full_response,
        "truncated": stop_reason == "max_tokens",
    })


def _build_api_messages(session: ConversationSession, augmented_message: str) -> list:
    """Build the Claude messages array from session history.

    Previous turns use their plain text; the current turn uses the augmented
    message. Images attach to the user message they were uploaded for.
    """
    messages = []
    for i, msg in enumerate(session.messages[:-1]):  # All previous messages
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

    # Current user message — may include an image
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

    return messages


def _build_augmented_message(
    user_message: str,
    url_contexts: list,
    template=None,
    has_course_context: bool = False,
) -> str:
    """Build the user message with deterministic context for Claude.

    Knowledge-base and past-case lookups are no longer injected here — the
    model fetches them via tools. Only cheap, deterministic context rides
    along with the message: parsed URLs, a detected diagnostic template, and
    a note about uploaded course context.
    """
    parts = []

    parts.append("## Support Issue")
    parts.append(user_message)

    url_text = format_url_context_for_llm(url_contexts)
    if url_text:
        parts.append(url_text)

    if template:
        parts.append("Use this diagnostic framework to structure your response:")
        parts.append(template.to_prompt_text())

    if has_course_context:
        parts.append(
            "*Note: course context (from an uploaded .mbz backup or saved "
            "page) is available — use the get_course_context tool if the "
            "issue relates to course configuration.*"
        )

    return "\n\n".join(parts)


def _detect_mode(response: str) -> str:
    """Heuristic mode detection — fallback when the model omits its
    MODE marker."""
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

    return "explore"


def _sse_event(event_type: str, data) -> str:
    """Format an SSE event string."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"
