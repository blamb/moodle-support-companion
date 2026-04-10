"""Diagnostic templates for common Moodle issue categories.

Each template provides structured diagnostic guidance: key questions to ask,
common causes ranked by likelihood, and resolution patterns. The conversation
service injects the relevant template into the Claude context when it detects
the issue category.
"""

from __future__ import annotations

import re
from typing import Optional, List, Dict


class DiagnosticTemplate:
    """A diagnostic template for a specific issue category."""

    def __init__(
        self,
        category: str,
        label: str,
        description: str,
        initial_questions: List[Dict[str, str]],
        common_causes: List[Dict[str, str]],
        resolution_patterns: List[str],
        key_settings_to_check: List[str],
    ):
        self.category = category
        self.label = label
        self.description = description
        self.initial_questions = initial_questions  # [{"type": "technologist"|"user", "question": "..."}]
        self.common_causes = common_causes  # [{"cause": "...", "likelihood": "high|medium|low", "check": "..."}]
        self.resolution_patterns = resolution_patterns
        self.key_settings_to_check = key_settings_to_check

    def to_prompt_text(self) -> str:
        """Format the template for injection into the Claude system prompt."""
        lines = [f"## Diagnostic Template: {self.label}"]
        lines.append(f"{self.description}\n")

        lines.append("### Key questions to explore")
        for q in self.initial_questions:
            icon = "🔧" if q["type"] == "technologist" else "💬"
            target = "FOR YOU" if q["type"] == "technologist" else "ASK THE USER"
            lines.append(f"- {icon} **{target}**: {q['question']}")

        lines.append("\n### Common causes (ranked by likelihood)")
        for c in self.common_causes:
            lines.append(f"- **[{c['likelihood'].upper()}]** {c['cause']}")
            lines.append(f"  Check: {c['check']}")

        lines.append("\n### Key Moodle settings to check")
        for s in self.key_settings_to_check:
            lines.append(f"- {s}")

        lines.append("\n### Common resolution patterns")
        for r in self.resolution_patterns:
            lines.append(f"- {r}")

        return "\n".join(lines)


# =============================================================================
# Template definitions
# =============================================================================

TEMPLATES: Dict[str, DiagnosticTemplate] = {}


def _register(t: DiagnosticTemplate):
    TEMPLATES[t.category] = t


# --- Gradebook / Grades ---
_register(DiagnosticTemplate(
    category="gradebook",
    label="Gradebook & Grade Visibility",
    description="Issues where grades are missing, hidden, incorrect, or not displaying as expected.",
    initial_questions=[
        {"type": "technologist", "question": "Check the Gradebook setup: Course > Grades > Setup tab. Is the grade item linked to the correct activity?"},
        {"type": "technologist", "question": "Is the grade item or grade category hidden (eye icon / 'Show' link)? Check both the item AND the category it belongs to."},
        {"type": "technologist", "question": "What is the aggregation method? (Course > Grades > Setup > Edit category). Natural weighting, weighted mean of grades, etc.?"},
        {"type": "user", "question": "Are you seeing this in the gradebook, or in the activity itself? Can you see your grade on the activity page?"},
        {"type": "user", "question": "Is this affecting all students or just you? Ask another student to check."},
    ],
    common_causes=[
        {"cause": "Grade item or category is hidden from students", "likelihood": "high",
         "check": "Gradebook > Setup > look for eye icon or 'Hidden' in the grade item row"},
        {"cause": "Quiz Review Options: 'Marks' unchecked for relevant review period", "likelihood": "high",
         "check": "Quiz settings > Review options > check 'Marks' columns"},
        {"cause": "Activity not yet graded (manual grading required)", "likelihood": "medium",
         "check": "Check the activity's grading interface for ungraded submissions"},
        {"cause": "Grade aggregation excluding empty grades", "likelihood": "medium",
         "check": "Category settings > 'Exclude empty grades' checkbox"},
        {"cause": "Grade item max/min mismatch between activity and gradebook", "likelihood": "low",
         "check": "Compare 'Maximum grade' in activity settings vs gradebook setup"},
        {"cause": "Role permissions preventing grade view", "likelihood": "low",
         "check": "Check moodle/grade:view capability for the student role"},
    ],
    key_settings_to_check=[
        "Course > Grades > Setup > Grade category aggregation method",
        "Course > Grades > Setup > Grade item visibility (hidden/show)",
        "Course > Grades > Preferences > Show/hide course total, grade percentages",
        "Quiz > Settings > Review options > Marks (per review period)",
        "Activity > Settings > Grade > Maximum grade",
    ],
    resolution_patterns=[
        "Unhide the grade item: Gradebook > Setup > click the eye icon to show",
        "Fix Quiz review options: Quiz settings > Review options > check 'Marks' for appropriate period",
        "Recalculate grades: Grades > Setup > Course grade settings > 'Recover grades default' or Force regrading",
        "Check role permissions at the course level for moodle/grade:view",
    ],
))


# --- Quiz Access & Visibility ---
_register(DiagnosticTemplate(
    category="quiz",
    label="Quiz Access & Visibility Issues",
    description="Issues where quizzes aren't visible, accessible, or behaving as expected for students.",
    initial_questions=[
        {"type": "technologist", "question": "Is the quiz shown/hidden on the course page? Check the edit menu (eye icon)."},
        {"type": "technologist", "question": "Check the quiz's Restrict Access settings (Availability conditions). Any date, grade, or group restrictions?"},
        {"type": "technologist", "question": "What are the quiz timing settings? Open date, close date, time limit?"},
        {"type": "user", "question": "Are you seeing the quiz on the course page at all, or is it completely missing?"},
        {"type": "user", "question": "If you can see it, what message do you get when you click on it?"},
        {"type": "user", "question": "Are you enrolled in a specific group in this course?"},
    ],
    common_causes=[
        {"cause": "Quiz is hidden from students (eye icon)", "likelihood": "high",
         "check": "Course page > Edit mode > check quiz visibility"},
        {"cause": "Restrict Access conditions not met (date, group, grade)", "likelihood": "high",
         "check": "Quiz settings > Restrict access section"},
        {"cause": "Quiz dates: not yet open or already closed", "likelihood": "high",
         "check": "Quiz settings > Timing section"},
        {"cause": "Quiz requires a password the student doesn't have", "likelihood": "medium",
         "check": "Quiz settings > Extra restrictions on attempts > Require password"},
        {"cause": "Quiz limited by group/grouping and student not in correct group", "likelihood": "medium",
         "check": "Quiz settings > Common module settings > Group mode, and Groups > Group membership"},
        {"cause": "Maximum attempts reached", "likelihood": "medium",
         "check": "Quiz settings > Attempts allowed, and check student's attempt count"},
        {"cause": "Student not enrolled in the course", "likelihood": "low",
         "check": "Course participants list > search for the student"},
    ],
    key_settings_to_check=[
        "Quiz > Settings > Timing (open, close, time limit)",
        "Quiz > Settings > Review options",
        "Quiz > Settings > Extra restrictions (password, network, browser security)",
        "Quiz > Settings > Restrict access (availability conditions)",
        "Quiz > Settings > Common module settings > Group mode",
        "Course > Participants > Student enrollment status",
    ],
    resolution_patterns=[
        "Show the quiz: Turn editing on > click eye icon to make visible",
        "Adjust Restrict Access: remove or modify conditions",
        "Extend quiz dates: Settings > Timing > adjust Open/Close",
        "Grant user override: Quiz > Overrides > add user override for dates/attempts",
        "Add student to correct group: Course > Participants > Groups",
    ],
))


# --- Assignment Submission & Grading ---
_register(DiagnosticTemplate(
    category="assignment",
    label="Assignment Submission & Grading",
    description="Issues with assignment submissions (can't submit, lost work, wrong format) or grading (marking guide, rubric, feedback).",
    initial_questions=[
        {"type": "technologist", "question": "What submission type is configured? (Online text, file submissions, both?) Check Assignment settings > Submission types."},
        {"type": "technologist", "question": "Check the assignment due date, cut-off date, and 'Submissions from' date in Availability settings."},
        {"type": "technologist", "question": "Is there a grading method set (Simple direct, Marking guide, Rubric)? Check Assignment > Settings > Grade > Grading method."},
        {"type": "user", "question": "What happens when you try to submit? Do you see an error message?"},
        {"type": "user", "question": "Did you click 'Submit assignment' after uploading your file? (Draft vs submitted status)"},
        {"type": "user", "question": "What file type and size are you trying to upload?"},
    ],
    common_causes=[
        {"cause": "Submission cut-off date has passed", "likelihood": "high",
         "check": "Assignment settings > Availability > Cut-off date"},
        {"cause": "Student submitted draft but didn't click 'Submit assignment'", "likelihood": "high",
         "check": "Check 'Require students to click submit button' setting and student's submission status"},
        {"cause": "File size exceeds maximum upload limit", "likelihood": "medium",
         "check": "Assignment settings > Submission types > Maximum file size"},
        {"cause": "File type not in accepted file types list", "likelihood": "medium",
         "check": "Assignment settings > Submission types > Accepted file types"},
        {"cause": "Grading form (rubric/marking guide) save issue — session timeout", "likelihood": "medium",
         "check": "Check if the grading session timed out (long time on grading page)"},
        {"cause": "Group assignment misconfiguration", "likelihood": "low",
         "check": "Assignment settings > Group submission settings"},
    ],
    key_settings_to_check=[
        "Assignment > Availability (due date, cut-off date, submissions from)",
        "Assignment > Submission types (online text, file, accepted types, max size)",
        "Assignment > Submission settings (require submit button, attempts reopened)",
        "Assignment > Grade > Grading method (Simple, Marking guide, Rubric)",
        "Assignment > Group submission settings",
    ],
    resolution_patterns=[
        "Extend cut-off date: Settings > Availability > adjust Cut-off date",
        "Grant extension: Assignment > View submissions > gear icon on student > Grant extension",
        "Reopen submission: View submissions > gear icon > Revert to draft",
        "Check session/timeout: if marking guide saves fail, try a different browser or clear cache",
        "Adjust file restrictions: Settings > Submission types > change accepted types or max size",
    ],
))


# --- Enrolment & Access ---
_register(DiagnosticTemplate(
    category="enrolment",
    label="Enrolment & Course Access",
    description="Issues where users can't access courses, see wrong content, or have incorrect roles.",
    initial_questions=[
        {"type": "technologist", "question": "Is the course visible to students? Check Course settings > Course visibility."},
        {"type": "technologist", "question": "What enrolment methods are active? Check Course > Participants > Enrolment methods."},
        {"type": "technologist", "question": "Check the specific user's enrolment: Course > Participants > search for user > check role, status (active/suspended), and enrolment start/end dates."},
        {"type": "user", "question": "When did you last access this course successfully?"},
        {"type": "user", "question": "Are you seeing a 'You cannot enrol yourself' message, a blank page, or something else?"},
    ],
    common_causes=[
        {"cause": "Course is hidden from students", "likelihood": "high",
         "check": "Course settings > Course visibility = Show/Hide"},
        {"cause": "Student not enrolled or enrolment suspended", "likelihood": "high",
         "check": "Participants list > search student > check Status column"},
        {"cause": "Enrolment has expired (end date passed)", "likelihood": "medium",
         "check": "Participants > student > Enrolment details > End date"},
        {"cause": "Self-enrolment disabled or requires enrolment key", "likelihood": "medium",
         "check": "Enrolment methods > Self enrolment > enabled/disabled, key required"},
        {"cause": "Course meta link / cohort sync not working", "likelihood": "low",
         "check": "Enrolment methods > check for meta/cohort enrolments and their source"},
        {"cause": "Student role missing required capabilities", "likelihood": "low",
         "check": "Course > Permissions > check student role capabilities"},
    ],
    key_settings_to_check=[
        "Course settings > Course visibility",
        "Course settings > Course start/end date",
        "Participants > Enrolment methods (self, manual, meta, cohort)",
        "Individual user's enrolment status, role, and dates",
        "Site administration > Plugins > Enrolment > manage enrolment plugins",
    ],
    resolution_patterns=[
        "Make course visible: Course settings > Course visibility > Show",
        "Manually enrol user: Participants > Enrol users button",
        "Reactivate enrolment: Participants > click user > Edit enrolment > change status to Active",
        "Extend enrolment: Participants > click user > Edit enrolment > adjust end date",
        "Enable self-enrolment: Enrolment methods > enable Self enrolment, set/remove key",
    ],
))


# --- Completion Tracking ---
_register(DiagnosticTemplate(
    category="completion",
    label="Completion Tracking Issues",
    description="Issues with activity completion, course completion, or completion-based restrictions not working.",
    initial_questions=[
        {"type": "technologist", "question": "Is completion tracking enabled at the course level? Check Course settings > Completion tracking = Yes."},
        {"type": "technologist", "question": "What completion conditions are set on the specific activity? Activity settings > Activity completion."},
        {"type": "technologist", "question": "Is cron running properly? Completion recalculation depends on scheduled tasks."},
        {"type": "user", "question": "Are you seeing a checkbox next to the activity? Is it greyed out or checkable?"},
        {"type": "user", "question": "Did you complete all the requirements for the activity (e.g., submitted assignment, achieved passing grade)?"},
    ],
    common_causes=[
        {"cause": "Completion tracking disabled at course level", "likelihood": "high",
         "check": "Course settings > Completion tracking"},
        {"cause": "Activity completion set to manual but student expects automatic", "likelihood": "high",
         "check": "Activity settings > Activity completion > Completion tracking dropdown"},
        {"cause": "Passing grade not set for grade-based completion", "likelihood": "medium",
         "check": "Activity settings > Grade > Grade to pass"},
        {"cause": "Cron job not running (completion not recalculated)", "likelihood": "medium",
         "check": "Site admin > Server > Scheduled tasks > check for stuck tasks"},
        {"cause": "Completion conditions changed after students already started", "likelihood": "low",
         "check": "Course completion > check for 'Reaggregate' option"},
    ],
    key_settings_to_check=[
        "Course settings > Completion tracking (enabled/disabled)",
        "Activity > Settings > Activity completion (type, conditions)",
        "Activity > Settings > Grade > Grade to pass (for grade-based completion)",
        "Course completion > Course completion criteria",
        "Site admin > Scheduled tasks > completion-related tasks",
    ],
    resolution_patterns=[
        "Enable course completion: Course settings > Completion tracking > Yes",
        "Fix activity completion: Activity settings > Completion tracking > set correct type and conditions",
        "Set passing grade: Activity > Grade > Grade to pass",
        "Force completion recalculation: Course completion > click 'Reaggregate' or run cron manually",
        "Reset completion for affected users: Course admin > Reports > Activity completion > select users > Reset",
    ],
))


# --- File & Content Issues ---
_register(DiagnosticTemplate(
    category="content",
    label="File & Content Display Issues",
    description="Issues with files not displaying, content not rendering, or media not playing.",
    initial_questions=[
        {"type": "technologist", "question": "What type of content/file is involved? (PDF, video, SCORM, H5P, embedded content?)"},
        {"type": "technologist", "question": "Check how the file/resource is displayed: in Moodle, in a popup, or forced download? Resource settings > Appearance > Display."},
        {"type": "user", "question": "What browser are you using? Have you tried a different browser?"},
        {"type": "user", "question": "Are you on campus or accessing from home? Are you using a VPN?"},
        {"type": "user", "question": "Do you see an error message, a blank page, or a spinning loader?"},
    ],
    common_causes=[
        {"cause": "Browser compatibility or caching issue", "likelihood": "high",
         "check": "Ask user to try incognito mode or clear cache"},
        {"cause": "File too large for upload/display limit", "likelihood": "medium",
         "check": "Check site upload limits: Site admin > Security > Site security settings > Maximum uploaded file size"},
        {"cause": "SCORM package compatibility issue", "likelihood": "medium",
         "check": "Check SCORM version (1.2 vs 2004), and SCORM settings > New window, Compatibility settings"},
        {"cause": "Mixed content (HTTP embedded in HTTPS page)", "likelihood": "medium",
         "check": "Check if embedded content uses http:// instead of https://"},
        {"cause": "File permissions / access restriction", "likelihood": "low",
         "check": "Check the file's availability/restrict access settings"},
    ],
    key_settings_to_check=[
        "Resource/File > Settings > Appearance > Display (embed, popup, force download)",
        "Site admin > Security > Maximum uploaded file size",
        "SCORM > Settings > Appearance, Compatibility, Grade method",
        "H5P > Settings > Display options",
        "Page/Label > Content editor > embedded media URLs (http vs https)",
    ],
    resolution_patterns=[
        "Clear cache / try incognito: most browser display issues resolve this way",
        "Re-upload file: sometimes files corrupt during upload, re-uploading fixes it",
        "Change display method: Resource settings > Display > try 'Automatic' or 'Open'",
        "Fix mixed content: update embedded URLs from http:// to https://",
        "SCORM: try 'New window' display, or adjust compatibility settings",
    ],
))


# =============================================================================
# Category detection
# =============================================================================

# Keywords and patterns that suggest each category
_CATEGORY_PATTERNS = {
    "gradebook": [
        r"\bgrade[sr]?\b", r"\bgradebook\b", r"\bgrading\b", r"\bmark[s]?\b",
        r"\bscore[s]?\b", r"\bgrade\s*report\b", r"\baggregat", r"\bweight",
        r"\bgrade\s*item\b", r"\bcourse\s*total\b", r"\bgrade\s*categor",
    ],
    "quiz": [
        r"\bquiz\b", r"\bquizzes\b", r"\bquestion\s*bank\b", r"\battempt[s]?\b",
        r"\btime\s*limit\b", r"\breview\s*option", r"\bquiz\s*report\b",
    ],
    "assignment": [
        r"\bassignment\b", r"\bsubmission[s]?\b", r"\bsubmit\b", r"\brubric\b",
        r"\bmarking\s*guide\b", r"\bdraft\b", r"\bfeedback\b", r"\bturnitin\b",
        r"\bcut[\s-]*off\b", r"\bdue\s*date\b",
    ],
    "enrolment": [
        r"\benrol", r"\benroll", r"\baccess\b.*\bcourse\b", r"\bcourse\b.*\baccess\b",
        r"\bcan'?t\s*(see|find|access)\b.*\bcourse\b", r"\bself[\s-]*enrol",
        r"\bparticipant[s]?\b", r"\brole[s]?\b.*\bassign", r"\bsuspend",
    ],
    "completion": [
        r"\bcompletion\b", r"\bcomplete[d]?\b.*\bactivity\b", r"\bprogress\b",
        r"\bcheckbox\b", r"\bcertificate\b.*\bcompletion\b", r"\brestrict.*\bcompletion\b",
    ],
    "content": [
        r"\bfile[s]?\b.*\b(display|show|open|download|upload)\b",
        r"\bscorm\b", r"\bh5p\b", r"\bvideo\b.*\b(play|load|display)\b",
        r"\bpdf\b.*\b(display|open|view)\b", r"\bblank\s*page\b",
        r"\bcontent\b.*\b(display|show|missing|broken)\b",
    ],
}


def detect_category(text: str) -> Optional[str]:
    """Detect the most likely issue category from message text.

    Returns the category key or None if no strong match.
    """
    text_lower = text.lower()
    scores: Dict[str, int] = {}

    for category, patterns in _CATEGORY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            score += len(matches)
        if score > 0:
            scores[category] = score

    if not scores:
        return None

    # Return the highest-scoring category if it has at least 2 matches
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best

    # If only 1 match, return it if the score is from a very specific keyword
    return best if scores[best] >= 1 else None


def get_template(category: str) -> Optional[DiagnosticTemplate]:
    """Get a diagnostic template by category."""
    return TEMPLATES.get(category)


def get_template_for_message(text: str) -> Optional[DiagnosticTemplate]:
    """Detect the category and return the matching template."""
    category = detect_category(text)
    if category:
        return get_template(category)
    return None
