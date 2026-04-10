"""SQLite database for case tracking with FTS5 full-text search."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from typing import Optional, List, Dict

from ..config import CASE_DB_PATH

logger = logging.getLogger(__name__)

_db_initialized = False


def _get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with proper settings."""
    CASE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CASE_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_database():
    """Initialize the database schema."""
    global _db_initialized
    if _db_initialized:
        return

    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                problem_description TEXT NOT NULL DEFAULT '',
                diagnosis TEXT NOT NULL DEFAULT '',
                resolution TEXT NOT NULL DEFAULT '',
                conversation_json TEXT NOT NULL DEFAULT '[]',
                tags TEXT NOT NULL DEFAULT '',
                difficulty INTEGER DEFAULT 0,
                moodle_module TEXT DEFAULT '',
                course_id TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'resolved'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
                summary,
                problem_description,
                diagnosis,
                resolution,
                tags,
                content='cases',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS cases_ai AFTER INSERT ON cases BEGIN
                INSERT INTO cases_fts(rowid, summary, problem_description, diagnosis, resolution, tags)
                VALUES (new.rowid, new.summary, new.problem_description, new.diagnosis, new.resolution, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS cases_ad AFTER DELETE ON cases BEGIN
                INSERT INTO cases_fts(cases_fts, rowid, summary, problem_description, diagnosis, resolution, tags)
                VALUES ('delete', old.rowid, old.summary, old.problem_description, old.diagnosis, old.resolution, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS cases_au AFTER UPDATE ON cases BEGIN
                INSERT INTO cases_fts(cases_fts, rowid, summary, problem_description, diagnosis, resolution, tags)
                VALUES ('delete', old.rowid, old.summary, old.problem_description, old.diagnosis, old.resolution, old.tags);
                INSERT INTO cases_fts(rowid, summary, problem_description, diagnosis, resolution, tags)
                VALUES (new.rowid, new.summary, new.problem_description, new.diagnosis, new.resolution, new.tags);
            END;
        """)
        conn.commit()
        _db_initialized = True
        logger.info(f"Case database initialized at {CASE_DB_PATH}")
    finally:
        conn.close()


def save_case(
    summary: str,
    problem_description: str = "",
    diagnosis: str = "",
    resolution: str = "",
    conversation: Optional[list] = None,
    tags: Optional[List[str]] = None,
    difficulty: int = 0,
    moodle_module: str = "",
    course_id: str = "",
    status: str = "resolved",
) -> str:
    """Save a new case. Returns the case ID."""
    import time

    case_id = str(uuid.uuid4())
    now = time.time()
    tags_str = ", ".join(tags) if tags else ""
    conversation_json = json.dumps(conversation or [])

    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO cases
            (id, created_at, updated_at, summary, problem_description,
             diagnosis, resolution, conversation_json, tags, difficulty,
             moodle_module, course_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, now, now, summary, problem_description,
             diagnosis, resolution, conversation_json, tags_str,
             difficulty, moodle_module, course_id, status),
        )
        conn.commit()
        logger.info(f"Saved case {case_id}: {summary[:50]}")
    finally:
        conn.close()

    return case_id


def search_cases(query: str, limit: int = 20) -> List[Dict]:
    """Search cases using FTS5 full-text search."""
    conn = _get_connection()
    try:
        # FTS5 query with ranking
        rows = conn.execute(
            """SELECT c.*, rank
            FROM cases_fts fts
            JOIN cases c ON c.rowid = fts.rowid
            WHERE cases_fts MATCH ?
            ORDER BY rank
            LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    except sqlite3.OperationalError:
        # Fallback to LIKE search if FTS query is invalid
        rows = conn.execute(
            """SELECT * FROM cases
            WHERE summary LIKE ? OR problem_description LIKE ?
            OR diagnosis LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def list_cases(limit: int = 50, offset: int = 0) -> List[Dict]:
    """List all cases, most recent first."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_case(case_id: str) -> Optional[Dict]:
    """Get a single case by ID."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_case(case_id: str, **kwargs) -> bool:
    """Update a case's fields."""
    import time

    allowed_fields = {
        "summary", "problem_description", "diagnosis", "resolution",
        "tags", "difficulty", "moodle_module", "course_id", "status",
    }

    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False

    # Convert tags list to string if needed
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = ", ".join(updates["tags"])

    updates["updated_at"] = time.time()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [case_id]

    conn = _get_connection()
    try:
        result = conn.execute(
            f"UPDATE cases SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def get_analytics() -> Dict:
    """Get aggregate analytics across all cases."""
    import time as _time

    conn = _get_connection()
    try:
        # Total counts
        total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM cases GROUP BY status"
        ).fetchall()

        # By difficulty
        by_difficulty = conn.execute(
            "SELECT difficulty, COUNT(*) as cnt FROM cases WHERE difficulty > 0 GROUP BY difficulty ORDER BY difficulty"
        ).fetchall()

        # By Moodle module
        by_module = conn.execute(
            "SELECT moodle_module, COUNT(*) as cnt FROM cases WHERE moodle_module != '' GROUP BY moodle_module ORDER BY cnt DESC"
        ).fetchall()

        # Tag frequency — tags are comma-separated strings
        all_tags_rows = conn.execute("SELECT tags FROM cases WHERE tags != ''").fetchall()
        tag_counts: Dict[str, int] = {}
        for row in all_tags_rows:
            for tag in row[0].split(","):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:20]

        # Timeline — cases per week for last 12 weeks
        twelve_weeks_ago = _time.time() - (12 * 7 * 86400)
        weekly_rows = conn.execute(
            """SELECT
                CAST((created_at - ?) / (7 * 86400) AS INTEGER) as week_num,
                COUNT(*) as cnt
            FROM cases
            WHERE created_at >= ?
            GROUP BY week_num
            ORDER BY week_num""",
            (twelve_weeks_ago, twelve_weeks_ago),
        ).fetchall()

        # Build weekly timeline with labels
        timeline = []
        now = _time.time()
        for i in range(12):
            week_start = twelve_weeks_ago + (i * 7 * 86400)
            label = _time.strftime("%b %d", _time.localtime(week_start))
            count = 0
            for row in weekly_rows:
                if row[0] == i:
                    count = row[1]
                    break
            timeline.append({"week": label, "count": count})

        # Average resolution — estimate from created_at to updated_at
        avg_row = conn.execute(
            "SELECT AVG(updated_at - created_at) FROM cases WHERE status = 'resolved'"
        ).fetchone()
        avg_resolution_hours = round((avg_row[0] or 0) / 3600, 1)

        # Recent trend — last 30 days vs previous 30 days
        thirty_days_ago = now - (30 * 86400)
        sixty_days_ago = now - (60 * 86400)
        recent_count = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE created_at >= ?", (thirty_days_ago,)
        ).fetchone()[0]
        previous_count = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE created_at >= ? AND created_at < ?",
            (sixty_days_ago, thirty_days_ago),
        ).fetchone()[0]

        return {
            "total_cases": total,
            "by_status": {row[0]: row[1] for row in by_status},
            "by_difficulty": {str(row[0]): row[1] for row in by_difficulty},
            "by_module": {row[0]: row[1] for row in by_module},
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "timeline": timeline,
            "avg_resolution_hours": avg_resolution_hours,
            "recent_30d": recent_count,
            "previous_30d": previous_count,
        }
    finally:
        conn.close()


def export_cases_csv() -> str:
    """Export all cases as CSV string."""
    import csv
    import io
    import time as _time

    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Case ID", "Created", "Updated", "Summary", "Problem Description",
            "Diagnosis", "Resolution", "Tags", "Difficulty", "Moodle Module",
            "Course ID", "Status"
        ])

        for row in rows:
            d = dict(row)
            writer.writerow([
                d.get("id", ""),
                _time.strftime("%Y-%m-%d %H:%M", _time.localtime(d.get("created_at", 0))),
                _time.strftime("%Y-%m-%d %H:%M", _time.localtime(d.get("updated_at", 0))),
                d.get("summary", ""),
                d.get("problem_description", ""),
                d.get("diagnosis", ""),
                d.get("resolution", ""),
                d.get("tags", ""),
                d.get("difficulty", 0),
                d.get("moodle_module", ""),
                d.get("course_id", ""),
                d.get("status", ""),
            ])

        return output.getvalue()
    finally:
        conn.close()


def list_all_tags() -> List[str]:
    """Get all unique tags across all cases."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT tags FROM cases WHERE tags != ''").fetchall()
        tag_set: set = set()
        for row in rows:
            for tag in row[0].split(","):
                tag = tag.strip()
                if tag:
                    tag_set.add(tag)
        return sorted(tag_set)
    finally:
        conn.close()


def list_cases_by_tag(tag: str, limit: int = 50, offset: int = 0) -> List[Dict]:
    """List cases that contain a specific tag."""
    conn = _get_connection()
    try:
        # Tags are stored as comma-separated strings
        rows = conn.execute(
            """SELECT * FROM cases
            WHERE ',' || tags || ',' LIKE ?
            ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
            (f"%,{tag},%", limit, offset),
        ).fetchall()

        # Also try without leading comma for first tag
        if not rows:
            rows = conn.execute(
                """SELECT * FROM cases
                WHERE tags LIKE ? OR tags LIKE ? OR tags = ?
                ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                (f"{tag},%", f"%, {tag}%", tag, limit, offset),
            ).fetchall()

        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict:
    """Convert a SQLite Row to a dict with parsed fields."""
    d = dict(row)
    # Parse conversation JSON
    if "conversation_json" in d:
        try:
            d["conversation"] = json.loads(d["conversation_json"])
        except json.JSONDecodeError:
            d["conversation"] = []
        del d["conversation_json"]
    # Parse tags string to list
    if "tags" in d and isinstance(d["tags"], str):
        d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    return d
