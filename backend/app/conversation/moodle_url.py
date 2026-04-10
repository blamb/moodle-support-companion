"""Moodle URL parser — extracts structured context from moodle.tru.ca URLs."""

from __future__ import annotations

import re
from typing import Optional, List
from urllib.parse import urlparse, parse_qs


# Known Moodle module types
MODULE_TYPES = {
    "assign": "Assignment",
    "quiz": "Quiz",
    "forum": "Forum",
    "resource": "File resource",
    "url": "URL resource",
    "page": "Page",
    "book": "Book",
    "folder": "Folder",
    "label": "Label",
    "lesson": "Lesson",
    "workshop": "Workshop",
    "wiki": "Wiki",
    "glossary": "Glossary",
    "data": "Database",
    "choice": "Choice",
    "feedback": "Feedback",
    "survey": "Survey",
    "chat": "Chat",
    "scorm": "SCORM package",
    "lti": "External tool (LTI)",
    "h5pactivity": "H5P activity",
    "bigbluebuttonbn": "BigBlueButton",
    "questionnaire": "Questionnaire",
    "checklist": "Checklist",
    "attendance": "Attendance",
    "scheduler": "Scheduler",
    "turnitintooltwo": "Turnitin",
    "coursecertificate": "Course certificate",
}

# Moodle URL domains to recognize
MOODLE_DOMAINS = {"moodle.tru.ca"}


class MoodleUrlContext:
    """Structured context extracted from a Moodle URL."""

    def __init__(
        self,
        url: str,
        module_type: Optional[str] = None,
        module_type_label: Optional[str] = None,
        course_id: Optional[int] = None,
        activity_id: Optional[int] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        section: Optional[str] = None,
        context_summary: str = "",
    ):
        self.url = url
        self.module_type = module_type
        self.module_type_label = module_type_label
        self.course_id = course_id
        self.activity_id = activity_id
        self.user_id = user_id
        self.action = action
        self.section = section
        self.context_summary = context_summary

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "module_type": self.module_type,
            "module_type_label": self.module_type_label,
            "course_id": self.course_id,
            "activity_id": self.activity_id,
            "user_id": self.user_id,
            "action": self.action,
            "section": self.section,
            "context_summary": self.context_summary,
        }


def _safe_int(value: Optional[str]) -> Optional[int]:
    """Safely convert a string to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _get_param(params: dict, key: str) -> Optional[str]:
    """Get first value of a query parameter."""
    values = params.get(key, [])
    return values[0] if values else None


def parse_single_url(url: str) -> Optional[MoodleUrlContext]:
    """Parse a single Moodle URL into structured context."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    # Check domain
    hostname = parsed.hostname or ""
    if hostname not in MOODLE_DOMAINS:
        return None

    path = parsed.path.rstrip("/")
    params = parse_qs(parsed.query)
    segments = [s for s in path.split("/") if s]

    ctx = MoodleUrlContext(url=url)
    summary_parts = []

    # Extract common params
    ctx.course_id = _safe_int(_get_param(params, "id")) if "course" in path else None
    ctx.user_id = _safe_int(_get_param(params, "userid"))

    # --- Module view: /mod/{type}/view.php ---
    if len(segments) >= 3 and segments[0] == "mod" and segments[2] == "view.php":
        mod_type = segments[1]
        ctx.module_type = mod_type
        ctx.module_type_label = MODULE_TYPES.get(mod_type, mod_type.title())
        ctx.activity_id = _safe_int(_get_param(params, "id"))

        action = _get_param(params, "action")
        if action:
            ctx.action = action
            if action == "grader" or action == "grading":
                summary_parts.append(f"{ctx.module_type_label} grading view")
                if ctx.user_id:
                    summary_parts.append(f"for user ID {ctx.user_id}")
            elif action == "editsubmission":
                summary_parts.append(f"{ctx.module_type_label} submission editing")
            else:
                summary_parts.append(f"{ctx.module_type_label} — action: {action}")
        else:
            summary_parts.append(f"{ctx.module_type_label} view")

        if ctx.activity_id:
            summary_parts.append(f"(activity ID {ctx.activity_id})")

    # --- Quiz review: /mod/quiz/review.php ---
    elif "mod/quiz/review.php" in path:
        ctx.module_type = "quiz"
        ctx.module_type_label = "Quiz"
        ctx.action = "review"
        attempt_id = _safe_int(_get_param(params, "attempt"))
        summary_parts.append("Quiz attempt review")
        if attempt_id:
            summary_parts.append(f"(attempt ID {attempt_id})")

    # --- Quiz report: /mod/quiz/report.php ---
    elif "mod/quiz/report.php" in path:
        ctx.module_type = "quiz"
        ctx.module_type_label = "Quiz"
        ctx.action = "report"
        mode = _get_param(params, "mode")
        ctx.activity_id = _safe_int(_get_param(params, "id"))
        summary_parts.append(f"Quiz report ({mode or 'overview'})")

    # --- Course view: /course/view.php ---
    elif "course/view.php" in path:
        ctx.course_id = _safe_int(_get_param(params, "id"))
        ctx.action = "view_course"
        summary_parts.append("Course page")
        if ctx.course_id:
            summary_parts.append(f"(course ID {ctx.course_id})")

    # --- Grade report: /grade/report/{type}/index.php ---
    elif "grade/report" in path:
        ctx.course_id = _safe_int(_get_param(params, "id"))
        ctx.action = "grade_report"
        # Extract report type from path
        for i, seg in enumerate(segments):
            if seg == "report" and i + 1 < len(segments):
                report_type = segments[i + 1]
                ctx.section = report_type
                summary_parts.append(f"Gradebook — {report_type} report")
                break
        if ctx.course_id:
            summary_parts.append(f"(course ID {ctx.course_id})")

    # --- Grade edit: /grade/edit/ ---
    elif "grade/edit" in path:
        ctx.course_id = _safe_int(_get_param(params, "id"))
        ctx.action = "grade_edit"
        summary_parts.append("Gradebook editing")

    # --- User profile: /user/view.php ---
    elif "user/view.php" in path:
        ctx.user_id = _safe_int(_get_param(params, "id"))
        ctx.course_id = _safe_int(_get_param(params, "course"))
        ctx.action = "view_user"
        summary_parts.append("User profile")
        if ctx.user_id:
            summary_parts.append(f"(user ID {ctx.user_id})")

    # --- Enrolment: /enrol/ ---
    elif path.startswith("/enrol"):
        ctx.course_id = _safe_int(_get_param(params, "id"))
        ctx.action = "enrolment"
        summary_parts.append("Enrolment management")

    # --- Activity editing: /course/modedit.php ---
    elif "course/modedit.php" in path:
        ctx.action = "edit_activity"
        update = _get_param(params, "update")
        if update:
            ctx.activity_id = _safe_int(update)
        summary_parts.append("Activity settings editor")

    # --- Course editing: /course/edit.php ---
    elif "course/edit.php" in path:
        ctx.course_id = _safe_int(_get_param(params, "id"))
        ctx.action = "edit_course"
        summary_parts.append("Course settings editor")

    # --- Admin pages: /admin/ ---
    elif path.startswith("/admin"):
        ctx.action = "admin"
        ctx.section = "/".join(segments[1:]) if len(segments) > 1 else "dashboard"
        summary_parts.append(f"Admin: {ctx.section}")

    # --- Backup/restore ---
    elif "backup" in path or "restore" in path:
        ctx.action = "backup_restore"
        ctx.course_id = _safe_int(_get_param(params, "id"))
        summary_parts.append("Backup/restore")

    # --- Report pages ---
    elif "report/" in path:
        ctx.action = "report"
        for i, seg in enumerate(segments):
            if seg == "report" and i + 1 < len(segments):
                ctx.section = segments[i + 1]
                summary_parts.append(f"Report: {ctx.section}")
                break

    # --- Fallback for any recognized Moodle URL ---
    else:
        summary_parts.append(f"Moodle page: {path}")

    ctx.context_summary = " ".join(summary_parts)
    return ctx


def parse_urls_from_text(text: str) -> List[MoodleUrlContext]:
    """Find and parse all Moodle URLs in a block of text."""
    # Match URLs with moodle.tru.ca domain
    url_pattern = r'https?://moodle\.tru\.ca[^\s<>"\')\]]*'
    urls = re.findall(url_pattern, text, re.IGNORECASE)

    contexts = []
    seen = set()
    for url in urls:
        # Clean trailing punctuation
        url = url.rstrip(".,;:!?")
        if url in seen:
            continue
        seen.add(url)

        ctx = parse_single_url(url)
        if ctx:
            contexts.append(ctx)

    return contexts


def format_url_context_for_llm(contexts: List[MoodleUrlContext]) -> str:
    """Format parsed URL contexts into text for the LLM system/user message."""
    if not contexts:
        return ""

    lines = ["## Moodle URL Context"]
    lines.append("The following URLs were detected in the message:\n")

    for ctx in contexts:
        lines.append(f"- **{ctx.context_summary}**")
        lines.append(f"  URL: {ctx.url}")
        if ctx.module_type:
            lines.append(f"  Module: {ctx.module_type_label} ({ctx.module_type})")
        if ctx.course_id:
            lines.append(f"  Course ID: {ctx.course_id}")
        if ctx.activity_id:
            lines.append(f"  Activity ID: {ctx.activity_id}")
        if ctx.user_id:
            lines.append(f"  User ID: {ctx.user_id}")
        lines.append("")

    return "\n".join(lines)
