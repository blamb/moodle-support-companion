"""Course health checker — analyzes .mbz course data for common misconfigurations.

Runs proactive diagnostics on course structure extracted from .mbz backups
to surface potential issues before they become support tickets.

Two layers:
- Rule-based checks (instant, free): hardcoded detection of known patterns
- AI audit (on demand): Claude reviews the full course structure for issues
  the rules don't cover — cross-referencing gradebook config, completion
  settings, and activity setup
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)


class HealthIssue:
    """A potential issue found in the course configuration."""

    SEVERITY_HIGH = "high"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_LOW = "low"
    SEVERITY_INFO = "info"

    def __init__(
        self,
        severity: str,
        category: str,
        title: str,
        description: str,
        suggestion: str = "",
    ):
        self.severity = severity
        self.category = category
        self.title = title
        self.description = description
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "suggestion": self.suggestion,
        }


def check_course_health(mbz_context) -> List[HealthIssue]:
    """Run all health checks on a parsed .mbz course context.

    Args:
        mbz_context: An MbzCourseContext object from mbz_parser.py
    """
    issues = []

    issues.extend(_check_completion(mbz_context))
    issues.extend(_check_gradebook(mbz_context))
    issues.extend(_check_activities(mbz_context))
    issues.extend(_check_structure(mbz_context))

    # Sort: high severity first
    severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    return issues


def format_health_report(issues: List[HealthIssue]) -> str:
    """Format health check results for display or LLM context."""
    if not issues:
        return "No issues found. Course configuration looks healthy."

    lines = [f"## Course Health Check: {len(issues)} issue(s) found\n"]

    severity_icons = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🔵",
        "info": "ℹ️",
    }

    for issue in issues:
        icon = severity_icons.get(issue.severity, "•")
        lines.append(f"{icon} **{issue.title}** ({issue.category})")
        lines.append(f"   {issue.description}")
        if issue.suggestion:
            lines.append(f"   → {issue.suggestion}")
        lines.append("")

    return "\n".join(lines)


def _check_completion(ctx) -> List[HealthIssue]:
    """Check completion tracking configuration."""
    issues = []

    if not ctx.completion_enabled:
        # Check if any activities might expect completion
        has_certificate = any(
            a.get("type") == "coursecertificate" for a in ctx.activities
        )
        if has_certificate:
            issues.append(HealthIssue(
                severity=HealthIssue.SEVERITY_HIGH,
                category="completion",
                title="Course certificate exists but completion tracking is disabled",
                description="A course certificate activity was found, but course completion tracking is disabled. The certificate likely won't be issued.",
                suggestion="Enable completion tracking: Course settings > Completion tracking > Yes",
            ))

    return issues


def _check_gradebook(ctx) -> List[HealthIssue]:
    """Check gradebook configuration."""
    issues = []

    # Check for grade items with no max grade or zero max
    for item in ctx.grade_items:
        grademax = item.get("grademax", "100")
        try:
            if float(grademax) == 0:
                issues.append(HealthIssue(
                    severity=HealthIssue.SEVERITY_MEDIUM,
                    category="gradebook",
                    title=f"Grade item '{item.get('name', 'unnamed')}' has maximum grade of 0",
                    description="This grade item has a maximum grade of 0, which means it won't contribute to the course total.",
                    suggestion="Set an appropriate maximum grade in the activity settings or gradebook setup.",
                ))
        except (ValueError, TypeError):
            pass

    # Check for grade categories with potentially confusing aggregation
    if len(ctx.grade_categories) > 2:
        issues.append(HealthIssue(
            severity=HealthIssue.SEVERITY_INFO,
            category="gradebook",
            title=f"Complex gradebook structure: {len(ctx.grade_categories)} grade categories",
            description="Multiple grade categories can make the gradebook harder for students to understand.",
            suggestion="Review the gradebook setup to ensure the category structure is clear and the aggregation methods are consistent.",
        ))

    # Check for orphaned grade items (type 'manual' with no module)
    manual_items = [i for i in ctx.grade_items if i.get("type") == "manual"]
    if manual_items:
        issues.append(HealthIssue(
            severity=HealthIssue.SEVERITY_LOW,
            category="gradebook",
            title=f"{len(manual_items)} manual grade item(s) found",
            description="Manual grade items are not linked to any activity. They must be graded directly in the gradebook.",
            suggestion="Verify these are intentional. If they should be linked to activities, recreate them through the activity settings.",
        ))

    return issues


def _check_activities(ctx) -> List[HealthIssue]:
    """Check activity configurations."""
    issues = []

    # Count activities by type
    type_counts: Dict[str, int] = {}
    for act in ctx.activities:
        t = act.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Check for large number of labels (often means poor course structure)
    label_count = type_counts.get("label", 0)
    if label_count > 20:
        issues.append(HealthIssue(
            severity=HealthIssue.SEVERITY_LOW,
            category="structure",
            title=f"High number of labels: {label_count}",
            description="Courses with many labels can be harder to navigate. Consider using Pages or Books for longer content.",
            suggestion="Review whether some labels could be consolidated or converted to Page resources.",
        ))

    # Check for activities with generic names
    generic_names = []
    for act in ctx.activities:
        name = act.get("name", "")
        if name and (
            name.lower().startswith(act.get("type", "")) or
            name == act.get("type", "").title() or
            len(name) < 4
        ):
            generic_names.append(f"{act.get('type')}: '{name}'")

    if generic_names:
        issues.append(HealthIssue(
            severity=HealthIssue.SEVERITY_LOW,
            category="structure",
            title=f"{len(generic_names)} activity(ies) with generic/default names",
            description=f"Some activities appear to have default or very short names: {', '.join(generic_names[:5])}",
            suggestion="Give activities descriptive names so students understand what they are.",
        ))

    return issues


def _check_structure(ctx) -> List[HealthIssue]:
    """Check overall course structure."""
    issues = []

    # Very large courses
    if len(ctx.activities) > 100:
        issues.append(HealthIssue(
            severity=HealthIssue.SEVERITY_MEDIUM,
            category="structure",
            title=f"Very large course: {len(ctx.activities)} activities",
            description="Courses with over 100 activities can be slow to load and overwhelming for students.",
            suggestion="Consider splitting content across multiple sections, using collapsible topics, or archiving unused activities.",
        ))

    # Course format considerations
    if ctx.course_format == "topics" and len(ctx.activities) > 50:
        issues.append(HealthIssue(
            severity=HealthIssue.SEVERITY_INFO,
            category="structure",
            title="Topics format with many activities",
            description="The Topics format shows all sections at once. With many activities, students may need to scroll extensively.",
            suggestion="Consider switching to a collapsible format (e.g., 'Collapsed Topics') or 'Grid' format for better navigation.",
        ))

    return issues


# ---------------------------------------------------------------------------
# AI audit — open-ended review of the course structure by Claude
# ---------------------------------------------------------------------------

_AUDIT_SYSTEM = """You are a Moodle 4.5 course configuration auditor for Thompson Rivers University's LT&I team. You review parsed course structure (from a .mbz backup) and identify configuration problems that could generate support tickets.

Focus on issues a rule-based checker would miss: cross-cutting problems (e.g. gradebook aggregation inconsistent with how activities are weighted, completion conditions that can never be satisfied, restricted-access chains that lock students out, quiz/assignment settings that conflict with the course's apparent design), not generic style advice.

Respond with ONLY a JSON array (no prose, no code fences). Each element:
{
  "severity": "high" | "medium" | "low" | "info",
  "category": "completion" | "gradebook" | "structure" | "activities" | "access",
  "title": "short title",
  "description": "what the problem is and why it matters",
  "suggestion": "specific fix, with the Moodle navigation path where possible"
}

Only report findings you have concrete evidence for in the provided structure. If the configuration looks healthy, return []."""

_VALID_SEVERITIES = {"high", "medium", "low", "info"}


async def ai_audit_course(
    course_context_text: str,
    rule_issues: List[HealthIssue] = None,
) -> List[HealthIssue]:
    """Run an open-ended AI audit of the course structure.

    Sends the parsed course summary to Claude and asks for findings beyond
    the rule-based checks. Returns additional HealthIssues (deduplicated
    against the rule-based findings by title). Fails soft: returns [] on
    any API or parsing error.
    """
    import anthropic
    from ..config import CLAUDE_MODEL

    already_found = ""
    if rule_issues:
        titles = "\n".join(f"- {i.title}" for i in rule_issues)
        already_found = (
            f"\n\nThe rule-based checker already reported these — do NOT repeat them:\n{titles}"
        )

    prompt = (
        "Audit this Moodle course configuration:\n\n"
        f"{course_context_text}{already_found}"
    )

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            system=_AUDIT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.warning(f"AI audit API call failed: {e}")
        return []

    if response.stop_reason == "refusal":
        logger.warning("AI audit was refused by the model")
        return []

    text = next((b.text for b in response.content if b.type == "text"), "")
    findings = _parse_audit_json(text)

    rule_titles = {i.title.lower() for i in (rule_issues or [])}
    issues = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        title = str(f.get("title", "")).strip()
        if not title or title.lower() in rule_titles:
            continue
        severity = str(f.get("severity", "info")).lower()
        if severity not in _VALID_SEVERITIES:
            severity = "info"
        issues.append(HealthIssue(
            severity=severity,
            category=str(f.get("category", "general")),
            title=title,
            description=str(f.get("description", "")),
            suggestion=str(f.get("suggestion", "")),
        ))

    severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))
    return issues


def _parse_audit_json(text: str) -> list:
    """Parse the audit response as a JSON array, tolerating code fences
    and surrounding prose."""
    text = text.strip()
    # Strip markdown code fences if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        pass
    # Last resort: extract the first [...] block
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass
    logger.warning("AI audit returned unparseable JSON")
    return []
