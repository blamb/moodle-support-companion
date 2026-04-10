"""Course health checker — analyzes .mbz course data for common misconfigurations.

Runs proactive diagnostics on course structure extracted from .mbz backups
to surface potential issues before they become support tickets.
"""

from __future__ import annotations

from typing import List, Dict


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
