"""SQLite persistence for diagnostic conversation sessions.

Sessions were previously held only in process memory and died on every
restart/deploy. This store write-throughs session state (messages, uploaded
course context, pending images) and share links to SQLite so sessions survive
restarts and can be restored from the frontend's recent-sessions list.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Optional

from ..config import SESSION_DB_PATH, SESSION_TTL

logger = logging.getLogger(__name__)

_initialized = False


def _get_connection() -> sqlite3.Connection:
    SESSION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SESSION_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_store():
    global _initialized
    if _initialized:
        return
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shared_links (
                share_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_shared_session
                ON shared_links(session_id);
        """)
        conn.commit()
        _initialized = True
    finally:
        conn.close()


def save_session(session_id: str, state: dict, created_at: float, updated_at: float):
    """Write-through a session's full state."""
    init_store()
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO sessions (id, data, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at""",
            (session_id, json.dumps(state, ensure_ascii=False), created_at, updated_at),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to persist session {session_id}: {e}")
    finally:
        conn.close()


def load_session(session_id: str) -> Optional[dict]:
    """Load a session's state, or None if missing/expired."""
    init_store()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT data, updated_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        if (time.time() - row["updated_at"]) > SESSION_TTL:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return None
        return json.loads(row["data"])
    except Exception as e:
        logger.warning(f"Failed to load session {session_id}: {e}")
        return None
    finally:
        conn.close()


def delete_session(session_id: str):
    init_store()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM shared_links WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def cleanup_expired():
    """Delete sessions past their TTL (and their share links)."""
    init_store()
    cutoff = time.time() - SESSION_TTL
    conn = _get_connection()
    try:
        conn.execute(
            """DELETE FROM shared_links WHERE session_id IN
            (SELECT id FROM sessions WHERE updated_at < ?)""",
            (cutoff,),
        )
        cur = conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
        conn.commit()
        if cur.rowcount:
            logger.info(f"Cleaned up {cur.rowcount} expired sessions")
    except Exception as e:
        logger.warning(f"Session cleanup failed: {e}")
    finally:
        conn.close()


def save_share_link(share_id: str, session_id: str):
    init_store()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO shared_links (share_id, session_id) VALUES (?, ?)",
            (share_id, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_share_link_for_session(session_id: str) -> Optional[str]:
    init_store()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT share_id FROM shared_links WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row["share_id"] if row else None
    finally:
        conn.close()


def resolve_share_link(share_id: str) -> Optional[str]:
    init_store()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT session_id FROM shared_links WHERE share_id = ?", (share_id,)
        ).fetchone()
        return row["session_id"] if row else None
    finally:
        conn.close()
