"""Parser for Moodle .mbz course backup files."""

from __future__ import annotations

import logging
import os
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class MbzCourseContext:
    """Structured context extracted from a .mbz course backup."""

    def __init__(self):
        self.course_name: str = ""
        self.course_shortname: str = ""
        self.course_format: str = ""
        self.moodle_version: str = ""
        self.backup_date: str = ""
        self.original_course_id: Optional[int] = None
        self.activities: List[Dict] = []
        self.grade_categories: List[Dict] = []
        self.grade_items: List[Dict] = []
        self.completion_enabled: bool = False
        self.sections: List[Dict] = []
        self.role_assignments: Dict[str, int] = {}

    @property
    def summary_text(self) -> str:
        """Generate a plaintext summary for injection into Claude context."""
        lines = []
        lines.append(f"Course: {self.course_name}")
        if self.course_shortname:
            lines.append(f"Short name: {self.course_shortname}")
        lines.append(f"Format: {self.course_format}")
        if self.moodle_version:
            lines.append(f"Moodle version: {self.moodle_version}")
        if self.original_course_id:
            lines.append(f"Course ID: {self.original_course_id}")

        if self.activities:
            lines.append(f"\nActivities ({len(self.activities)} total):")
            # Group by type
            by_type: Dict[str, List[str]] = {}
            for act in self.activities:
                mod_type = act.get("type", "unknown")
                name = act.get("name", "untitled")
                by_type.setdefault(mod_type, []).append(name)

            for mod_type, names in sorted(by_type.items()):
                lines.append(f"  {mod_type} ({len(names)}):")
                for name in names[:10]:  # Limit to 10 per type
                    lines.append(f"    - {name}")
                if len(names) > 10:
                    lines.append(f"    ... and {len(names) - 10} more")

        if self.grade_categories:
            lines.append(f"\nGrade categories ({len(self.grade_categories)}):")
            for cat in self.grade_categories:
                agg = cat.get("aggregation", "")
                lines.append(f"  - {cat.get('name', 'unnamed')} (aggregation: {agg})")

        if self.grade_items:
            lines.append(f"\nGrade items ({len(self.grade_items)}):")
            for item in self.grade_items[:20]:
                lines.append(
                    f"  - {item.get('name', 'unnamed')} "
                    f"(type: {item.get('type', '?')}, "
                    f"max: {item.get('grademax', '?')})"
                )
            if len(self.grade_items) > 20:
                lines.append(f"  ... and {len(self.grade_items) - 20} more")

        if self.completion_enabled:
            lines.append("\nCompletion tracking: enabled")

        if self.role_assignments:
            lines.append("\nRole assignments:")
            for role, count in self.role_assignments.items():
                lines.append(f"  - {role}: {count}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "course_name": self.course_name,
            "course_shortname": self.course_shortname,
            "course_format": self.course_format,
            "moodle_version": self.moodle_version,
            "original_course_id": self.original_course_id,
            "activity_count": len(self.activities),
            "activity_types": list(set(a.get("type", "") for a in self.activities)),
            "grade_category_count": len(self.grade_categories),
            "grade_item_count": len(self.grade_items),
            "completion_enabled": self.completion_enabled,
            "summary": self.summary_text,
        }


def _get_xml_text(element: Optional[ET.Element], tag: str, default: str = "") -> str:
    """Safely get text content of a child element."""
    if element is None:
        return default
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def parse_mbz_file(file_path: str) -> MbzCourseContext:
    """Parse a .mbz file and extract course context.

    The .mbz file is a gzip tar archive containing XML files.
    """
    ctx = MbzCourseContext()
    tmp_dir = tempfile.mkdtemp(prefix="mbz_")

    try:
        # Extract the archive
        with tarfile.open(file_path, "r:gz") as tar:
            # Security: prevent path traversal
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    continue
                # Skip the files/ directory (binary content, can be huge)
                if member.name.startswith("files/"):
                    continue
                tar.extract(member, tmp_dir, filter="data")

        # Parse moodle_backup.xml
        backup_xml = os.path.join(tmp_dir, "moodle_backup.xml")
        if os.path.exists(backup_xml):
            _parse_backup_xml(backup_xml, ctx)

        # Parse course/course.xml
        course_xml = os.path.join(tmp_dir, "course", "course.xml")
        if os.path.exists(course_xml):
            _parse_course_xml(course_xml, ctx)

        # Parse activity directories
        activities_dir = os.path.join(tmp_dir, "activities")
        if os.path.exists(activities_dir):
            _parse_activities(activities_dir, ctx)

        # Parse gradebook.xml
        gradebook_xml = os.path.join(tmp_dir, "gradebook.xml")
        if os.path.exists(gradebook_xml):
            _parse_gradebook(gradebook_xml, ctx)

        # Parse completion.xml
        completion_xml = os.path.join(tmp_dir, "completion.xml")
        if os.path.exists(completion_xml):
            _parse_completion(completion_xml, ctx)

        # Parse roles.xml
        roles_xml = os.path.join(tmp_dir, "roles.xml")
        if os.path.exists(roles_xml):
            _parse_roles(roles_xml, ctx)

        logger.info(
            f"Parsed .mbz: {ctx.course_name} — "
            f"{len(ctx.activities)} activities, "
            f"{len(ctx.grade_items)} grade items"
        )

    except tarfile.ReadError as e:
        logger.error(f"Failed to read .mbz file: {e}")
        raise ValueError(f"Invalid .mbz file: {e}")
    except Exception as e:
        logger.error(f"Error parsing .mbz: {e}")
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return ctx


def _parse_backup_xml(path: str, ctx: MbzCourseContext):
    """Parse moodle_backup.xml for course metadata and activity list."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Course info from information section
        info = root.find(".//information")
        if info is not None:
            ctx.moodle_version = _get_xml_text(info, "moodle_release")
            ctx.original_course_id = int(_get_xml_text(info, "original_course_id", "0") or "0")

            detail = info.find("details/detail")
            if detail is not None:
                backup_type = _get_xml_text(detail, "type")

        # Course name from contents
        course_el = root.find(".//contents/course")
        if course_el is not None:
            ctx.course_name = _get_xml_text(course_el, "title", ctx.course_name)

        # Activities from contents
        for activity in root.findall(".//contents/activities/activity"):
            act_data = {
                "type": _get_xml_text(activity, "modulename"),
                "name": _get_xml_text(activity, "title"),
                "id": _get_xml_text(activity, "moduleid"),
                "section_id": _get_xml_text(activity, "sectionid"),
                "directory": _get_xml_text(activity, "directory"),
            }
            if act_data["type"]:
                ctx.activities.append(act_data)

    except ET.ParseError as e:
        logger.warning(f"Error parsing moodle_backup.xml: {e}")


def _parse_course_xml(path: str, ctx: MbzCourseContext):
    """Parse course/course.xml for course settings."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        course = root.find("course") if root.tag != "course" else root
        if course is not None:
            ctx.course_name = _get_xml_text(course, "fullname", ctx.course_name)
            ctx.course_shortname = _get_xml_text(course, "shortname")
            ctx.course_format = _get_xml_text(course, "format", "unknown")
            completion = _get_xml_text(course, "enablecompletion", "0")
            ctx.completion_enabled = completion == "1"
    except ET.ParseError as e:
        logger.warning(f"Error parsing course.xml: {e}")


def _parse_activities(activities_dir: str, ctx: MbzCourseContext):
    """Parse individual activity directories for settings."""
    for dirname in os.listdir(activities_dir):
        act_dir = os.path.join(activities_dir, dirname)
        if not os.path.isdir(act_dir):
            continue

        # Parse module.xml for common settings
        module_xml = os.path.join(act_dir, "module.xml")
        if os.path.exists(module_xml):
            try:
                tree = ET.parse(module_xml)
                root = tree.getroot()
                # We could extract visibility, completion settings, etc.
                # For now, activity list comes from moodle_backup.xml
            except ET.ParseError:
                pass


def _parse_gradebook(path: str, ctx: MbzCourseContext):
    """Parse gradebook.xml for grade structure."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Grade categories
        for cat in root.findall(".//grade_categories/grade_category"):
            ctx.grade_categories.append({
                "name": _get_xml_text(cat, "fullname", "Course total"),
                "aggregation": _get_xml_text(cat, "aggregation", "unknown"),
                "depth": _get_xml_text(cat, "depth", "0"),
            })

        # Grade items
        for item in root.findall(".//grade_items/grade_item"):
            item_type = _get_xml_text(item, "itemtype")
            ctx.grade_items.append({
                "name": _get_xml_text(item, "itemname", "unnamed"),
                "type": item_type,
                "module": _get_xml_text(item, "itemmodule"),
                "grademax": _get_xml_text(item, "grademax", "100"),
                "grademin": _get_xml_text(item, "grademin", "0"),
                "aggregationcoef": _get_xml_text(item, "aggregationcoef", "0"),
            })

    except ET.ParseError as e:
        logger.warning(f"Error parsing gradebook.xml: {e}")


def _parse_completion(path: str, ctx: MbzCourseContext):
    """Parse completion.xml for completion tracking settings."""
    try:
        tree = ET.parse(path)
        # If the file exists and has content, completion is configured
        root = tree.getroot()
        if root.find(".//completion") is not None or len(root) > 0:
            ctx.completion_enabled = True
    except ET.ParseError:
        pass


def _parse_roles(path: str, ctx: MbzCourseContext):
    """Parse roles.xml for role assignment counts."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        for role in root.findall(".//role"):
            role_name = role.get("name", "") or _get_xml_text(role, "name", "")
            # Count assignments
            assignments = role.findall(".//assignment")
            if role_name and assignments:
                ctx.role_assignments[role_name] = len(assignments)

    except ET.ParseError as e:
        logger.warning(f"Error parsing roles.xml: {e}")
