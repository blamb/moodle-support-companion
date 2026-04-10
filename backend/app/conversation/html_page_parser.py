"""Parser for saved Moodle HTML pages.

Extracts structured information from Moodle pages saved via browser
(Cmd+S / Ctrl+S), including course structure, activity settings,
gradebook data, user lists, and error messages.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Dict, List

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MoodlePageContext:
    """Structured context extracted from a saved Moodle HTML page."""

    def __init__(self):
        self.page_title: str = ""
        self.page_type: str = ""  # course, activity_settings, gradebook, user_list, error, etc.
        self.breadcrumb: List[str] = []
        self.course_name: str = ""
        self.settings: Dict[str, str] = {}
        self.tables: List[Dict] = []
        self.error_messages: List[str] = []
        self.notifications: List[str] = []
        self.content_text: str = ""
        self.activity_type: str = ""
        self.user_role: str = ""

    @property
    def summary_text(self) -> str:
        """Generate a summary for injection into the conversation context."""
        lines = []
        lines.append(f"## Moodle Page Context (from saved HTML)")
        lines.append(f"**Page**: {self.page_title}")

        if self.breadcrumb:
            lines.append(f"**Path**: {' > '.join(self.breadcrumb)}")
        if self.course_name:
            lines.append(f"**Course**: {self.course_name}")
        if self.page_type:
            lines.append(f"**Page type**: {self.page_type}")
        if self.activity_type:
            lines.append(f"**Activity**: {self.activity_type}")

        if self.error_messages:
            lines.append(f"\n**Errors found:**")
            for err in self.error_messages:
                lines.append(f"- {err}")

        if self.notifications:
            lines.append(f"\n**Notifications:**")
            for note in self.notifications:
                lines.append(f"- {note}")

        if self.settings:
            lines.append(f"\n**Settings visible on page:**")
            for key, val in list(self.settings.items())[:30]:  # Limit
                lines.append(f"- {key}: {val}")
            if len(self.settings) > 30:
                lines.append(f"- ... and {len(self.settings) - 30} more settings")

        if self.tables:
            for table in self.tables[:3]:  # Limit to 3 tables
                header = table.get("header", "")
                rows = table.get("rows", [])
                if header:
                    lines.append(f"\n**{header}** ({len(rows)} rows)")
                for row in rows[:15]:  # Limit rows
                    lines.append(f"  {row}")
                if len(rows) > 15:
                    lines.append(f"  ... and {len(rows) - 15} more rows")

        if self.content_text and not self.settings and not self.tables:
            # Only include raw text if we didn't extract structured data
            truncated = self.content_text[:2000]
            lines.append(f"\n**Page content:**\n{truncated}")
            if len(self.content_text) > 2000:
                lines.append("... (truncated)")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "page_title": self.page_title,
            "page_type": self.page_type,
            "breadcrumb": self.breadcrumb,
            "course_name": self.course_name,
            "activity_type": self.activity_type,
            "settings_count": len(self.settings),
            "tables_count": len(self.tables),
            "errors": self.error_messages,
            "notifications": self.notifications,
            "summary": self.summary_text,
        }


def parse_moodle_html(html_content: str) -> MoodlePageContext:
    """Parse a saved Moodle HTML page and extract structured context."""
    ctx = MoodlePageContext()
    soup = BeautifulSoup(html_content, "lxml")

    # Extract page title
    title_tag = soup.find("title")
    if title_tag:
        ctx.page_title = title_tag.get_text(strip=True)

    # Extract breadcrumb navigation
    _extract_breadcrumb(soup, ctx)

    # Extract course name
    _extract_course_name(soup, ctx)

    # Detect page type
    _detect_page_type(soup, ctx)

    # Extract error messages
    _extract_errors(soup, ctx)

    # Extract notifications/alerts
    _extract_notifications(soup, ctx)

    # Extract settings forms
    _extract_settings(soup, ctx)

    # Extract data tables
    _extract_tables(soup, ctx)

    # Extract main content as fallback
    if not ctx.settings and not ctx.tables:
        _extract_content(soup, ctx)

    logger.info(
        f"Parsed Moodle page: {ctx.page_title} "
        f"(type: {ctx.page_type}, {len(ctx.settings)} settings, "
        f"{len(ctx.tables)} tables)"
    )

    return ctx


def _extract_breadcrumb(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract the breadcrumb navigation path."""
    breadcrumb = soup.find("nav", {"aria-label": "Navigation bar"})
    if not breadcrumb:
        breadcrumb = soup.find("ol", class_="breadcrumb")
    if not breadcrumb:
        breadcrumb = soup.find("div", class_="breadcrumb")

    if breadcrumb:
        items = breadcrumb.find_all("li")
        if not items:
            items = breadcrumb.find_all("a")
        ctx.breadcrumb = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]


def _extract_course_name(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract the course name from page elements."""
    # Try the header/course name area
    course_header = soup.find("div", class_="page-header-headings")
    if course_header:
        h1 = course_header.find("h1")
        if h1:
            ctx.course_name = h1.get_text(strip=True)
            return

    # Try breadcrumb — course name is usually the second-to-last item
    if len(ctx.breadcrumb) >= 2:
        ctx.course_name = ctx.breadcrumb[1] if ctx.breadcrumb[0].lower() in ("home", "dashboard", "my courses") else ctx.breadcrumb[0]


def _detect_page_type(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Detect what type of Moodle page this is."""
    body = soup.find("body")
    body_class = body.get("class", []) if body else []
    body_class_str = " ".join(body_class) if isinstance(body_class, list) else str(body_class)
    body_id = body.get("id", "") if body else ""

    title_lower = ctx.page_title.lower()

    if "grade" in title_lower or "grader" in body_class_str:
        ctx.page_type = "gradebook"
    elif "edit" in title_lower and ("settings" in title_lower or "updating" in title_lower):
        ctx.page_type = "activity_settings"
    elif "participants" in title_lower or "enrolled" in title_lower:
        ctx.page_type = "participants"
    elif "course" in body_class_str and "view" in body_class_str:
        ctx.page_type = "course_page"
    elif "error" in title_lower or "exception" in title_lower:
        ctx.page_type = "error_page"
    elif "quiz" in title_lower or "quiz" in body_class_str:
        ctx.page_type = "quiz"
        ctx.activity_type = "quiz"
    elif "assign" in body_class_str:
        ctx.page_type = "assignment"
        ctx.activity_type = "assign"
    elif "forum" in body_class_str:
        ctx.page_type = "forum"
        ctx.activity_type = "forum"
    elif "completion" in title_lower:
        ctx.page_type = "completion"
    elif "enrol" in title_lower:
        ctx.page_type = "enrolment"
    else:
        ctx.page_type = "other"

    # Try to detect activity type from body classes
    for cls in body_class if isinstance(body_class, list) else body_class_str.split():
        if cls.startswith("path-mod-"):
            ctx.activity_type = cls.replace("path-mod-", "")
            break


def _extract_errors(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract error messages from the page."""
    # Moodle error notifications
    for el in soup.find_all(class_=re.compile(r"(alert-danger|error|notification-error|errormessage)")):
        text = el.get_text(strip=True)
        if text and len(text) > 5:
            ctx.error_messages.append(text[:500])

    # Error box
    error_box = soup.find("div", class_="errorbox")
    if error_box:
        text = error_box.get_text(strip=True)
        if text:
            ctx.error_messages.append(text[:500])

    # Debug/stack trace info
    debug_info = soup.find("div", class_="debugging")
    if debug_info:
        text = debug_info.get_text(strip=True)
        if text:
            ctx.error_messages.append(f"Debug info: {text[:500]}")


def _extract_notifications(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract notification/alert messages."""
    for el in soup.find_all(class_=re.compile(r"(alert-warning|alert-info|alert-success|notification)")):
        text = el.get_text(strip=True)
        if text and len(text) > 5 and text not in ctx.error_messages:
            ctx.notifications.append(text[:300])


def _extract_settings(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract form settings from settings/edit pages."""
    # Look for Moodle settings forms
    forms = soup.find_all("form", class_=re.compile(r"(mform|mod-form)"))
    if not forms:
        forms = soup.find_all("form", id=re.compile(r"(mform|adminsettings)"))

    for form in forms:
        # Extract fieldset/section groups
        for fieldset in form.find_all("fieldset"):
            legend = fieldset.find("legend")
            section_name = legend.get_text(strip=True) if legend else ""

            for group in fieldset.find_all("div", class_="fitem"):
                label_el = group.find("label")
                if not label_el:
                    label_el = group.find("div", class_="fitemtitle")

                label = label_el.get_text(strip=True) if label_el else ""
                if not label:
                    continue

                # Get the value
                value = _extract_form_value(group)
                if value:
                    key = f"{section_name} > {label}" if section_name else label
                    ctx.settings[key] = value


def _extract_form_value(container) -> str:
    """Extract the current value from a form field container."""
    # Select element
    select = container.find("select")
    if select:
        selected = select.find("option", selected=True)
        if selected:
            return selected.get_text(strip=True)

    # Input element
    inp = container.find("input", type=re.compile(r"(text|number|date|url)"))
    if inp and inp.get("value"):
        return inp["value"]

    # Checkbox
    checkbox = container.find("input", type="checkbox")
    if checkbox:
        return "Checked" if checkbox.get("checked") else "Not checked"

    # Radio buttons
    for radio in container.find_all("input", type="radio"):
        if radio.get("checked"):
            label = radio.find_next("label")
            return label.get_text(strip=True) if label else "Selected"

    # Static text display
    static = container.find("div", class_="fstatic")
    if not static:
        static = container.find("span", class_="fstatic")
    if static:
        return static.get_text(strip=True)

    return ""


def _extract_tables(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract data tables (gradebook, participants, etc.)."""
    main_content = soup.find("div", id="region-main") or soup.find("div", role="main") or soup

    for table in main_content.find_all("table", class_=re.compile(r"(generaltable|gradestable|userlist|flexible)")):
        table_data = {"header": "", "rows": []}

        # Get table caption or preceding heading
        caption = table.find("caption")
        if caption:
            table_data["header"] = caption.get_text(strip=True)
        else:
            prev = table.find_previous(["h2", "h3", "h4"])
            if prev:
                table_data["header"] = prev.get_text(strip=True)

        # Extract header row
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]
            if headers:
                table_data["rows"].append(" | ".join(headers))
                table_data["rows"].append("-" * 40)

        # Extract data rows
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr", recursive=False):
            cells = [td.get_text(strip=True)[:100] for td in tr.find_all(["td", "th"])]
            if cells and any(c for c in cells):
                table_data["rows"].append(" | ".join(cells))

        if table_data["rows"]:
            ctx.tables.append(table_data)


def _extract_content(soup: BeautifulSoup, ctx: MoodlePageContext):
    """Extract main content text as a fallback."""
    main = soup.find("div", id="region-main") or soup.find("div", role="main")
    if main:
        # Remove scripts, styles, nav
        for el in main.find_all(["script", "style", "nav", "header", "footer"]):
            el.decompose()
        ctx.content_text = main.get_text(separator="\n", strip=True)[:5000]
