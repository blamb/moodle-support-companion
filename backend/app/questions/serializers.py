"""Serialize :class:`Question` objects into Moodle import formats.

Three formats are supported, matching what Moodle's question bank can import:

- **GIFT** (``.txt``) — the most expressive plain-text format; handles every
  type we produce.
- **Moodle XML** (``.xml``) — the safest, most complete format; preferred for
  anything with rich text or feedback.
- **Aiken** (``.txt``) — multiple-choice / true-false only; simplest for
  instructors but lossy, so unsupported questions are reported, never dropped
  silently.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import (
    Question,
    QTYPE_MULTICHOICE,
    QTYPE_TRUEFALSE,
    QTYPE_SHORTANSWER,
    QTYPE_ESSAY,
    QTYPE_MATCHING,
    QTYPE_NUMERICAL,
)


# --------------------------------------------------------------------------- #
# GIFT
# --------------------------------------------------------------------------- #

# Characters that carry special meaning in GIFT and must be backslash-escaped
# wherever they appear in literal text. Order matters: escape backslash first.
_GIFT_SPECIAL = ["\\", "~", "=", "#", "{", "}", ":"]


def _gift_escape(text: str) -> str:
    out = text
    for ch in _GIFT_SPECIAL:
        out = out.replace(ch, "\\" + ch)
    return out


def _fmt_fraction(fraction: float) -> str:
    """Format a percentage for GIFT (drop trailing .0)."""
    if fraction == int(fraction):
        return str(int(fraction))
    return ("%g" % fraction)


def _gift_question(q: Question) -> str:
    name = _gift_escape(q.display_name())
    stem = _gift_escape(q.text)
    header = f"::{name}::{stem} "

    if q.qtype == QTYPE_ESSAY:
        return header + "{}\n"

    if q.qtype == QTYPE_TRUEFALSE:
        tf = "T" if (q.correct or "").lower().startswith("t") else "F"
        return header + "{" + tf + "}\n"

    if q.qtype == QTYPE_SHORTANSWER:
        lines = ["{"]
        for a in q.answers:
            frac = "" if a.fraction == 100 else f"%{_fmt_fraction(a.fraction)}%"
            lines.append(f"\t={frac}{_gift_escape(a.text)}")
        lines.append("}")
        return header + "\n".join(lines) + "\n"

    if q.qtype == QTYPE_NUMERICAL:
        lines = ["{#"]
        for a in q.answers:
            tol = a.tolerance if a.tolerance is not None else 0
            frac = "" if a.fraction == 100 else f"%{_fmt_fraction(a.fraction)}%"
            lines.append(f"\t={frac}{_gift_escape(a.text)}:{_fmt_fraction(tol)}")
        lines.append("}")
        return header + "\n".join(lines) + "\n"

    if q.qtype == QTYPE_MATCHING:
        lines = ["{"]
        for p in q.pairs:
            lines.append(f"\t={_gift_escape(p.question)} -> {_gift_escape(p.answer)}")
        lines.append("}")
        return header + "\n".join(lines) + "\n"

    # Multiple choice (single or multiple answer)
    lines = ["{"]
    # A clean single-answer question (exactly one 100% option, rest 0) can use
    # the simple =/~ notation; anything else uses explicit ~%fraction%.
    simple = (
        q.single
        and sum(1 for o in q.options if o.fraction == 100) == 1
        and all(o.fraction in (0, 100) for o in q.options)
    )
    for o in q.options:
        text = _gift_escape(o.text)
        fb = f" # {_gift_escape(o.feedback)}" if o.feedback else ""
        if simple:
            marker = "=" if o.fraction == 100 else "~"
            lines.append(f"\t{marker}{text}{fb}")
        else:
            lines.append(f"\t~%{_fmt_fraction(o.fraction)}%{text}{fb}")
    lines.append("}")
    return header + "\n".join(lines) + "\n"


def to_gift(questions: List[Question]) -> str:
    return "\n".join(_gift_question(q) for q in questions)


# --------------------------------------------------------------------------- #
# Moodle XML
# --------------------------------------------------------------------------- #

def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _cdata(text: str) -> str:
    # Guard against the (extremely rare) literal "]]>" inside content.
    safe = (text or "").replace("]]>", "]]&gt;")
    return f"<![CDATA[{safe}]]>"


def _xml_questiontext(text: str) -> str:
    # Wrap plain text in a paragraph so Moodle renders it sensibly.
    body = text if "<" in text else f"<p>{text}</p>"
    return (
        '    <questiontext format="html">\n'
        f"      <text>{_cdata(body)}</text>\n"
        "    </questiontext>\n"
    )


def _xml_general_feedback(feedback: str) -> str:
    if not feedback:
        return ""
    return (
        '    <generalfeedback format="html">\n'
        f"      <text>{_cdata(feedback)}</text>\n"
        "    </generalfeedback>\n"
    )


def _xml_answer(text: str, fraction: float, feedback: str = "") -> str:
    out = f'    <answer fraction="{_fmt_fraction(fraction)}" format="html">\n'
    out += f"      <text>{_cdata(text if '<' in text else f'<p>{text}</p>')}</text>\n"
    if feedback:
        out += f"      <feedback format=\"html\"><text>{_cdata(feedback)}</text></feedback>\n"
    out += "    </answer>\n"
    return out


def _xml_question(q: Question) -> str:
    name = _xml_escape(q.display_name())
    head = (
        f'  <question type="{q.qtype}">\n'
        f"    <name><text>{name}</text></name>\n"
        + _xml_questiontext(q.text)
        + _xml_general_feedback(q.feedback)
        + "    <defaultgrade>1.0000000</defaultgrade>\n"
    )

    if q.qtype == QTYPE_ESSAY:
        body = (
            "    <responseformat>editor</responseformat>\n"
            "    <responserequired>1</responserequired>\n"
            "    <responsefieldlines>10</responsefieldlines>\n"
            "    <attachments>0</attachments>\n"
        )
        return head + body + "  </question>\n"

    if q.qtype == QTYPE_TRUEFALSE:
        is_true = (q.correct or "").lower().startswith("t")
        body = (
            _xml_answer("true", 100 if is_true else 0)
            + _xml_answer("false", 0 if is_true else 100)
        )
        return head + body + "  </question>\n"

    if q.qtype == QTYPE_SHORTANSWER:
        body = "    <usecase>0</usecase>\n"
        for a in q.answers:
            body += _xml_answer(a.text, a.fraction)
        return head + body + "  </question>\n"

    if q.qtype == QTYPE_NUMERICAL:
        body = ""
        for a in q.answers:
            tol = a.tolerance if a.tolerance is not None else 0
            body += f'    <answer fraction="{_fmt_fraction(a.fraction)}">\n'
            body += f"      <text>{_xml_escape(a.text)}</text>\n"
            body += f"      <tolerance>{_fmt_fraction(tol)}</tolerance>\n"
            body += "    </answer>\n"
        return head + body + "  </question>\n"

    if q.qtype == QTYPE_MATCHING:
        body = '    <shuffleanswers>true</shuffleanswers>\n'
        for p in q.pairs:
            body += "    <subquestion format=\"html\">\n"
            body += f"      <text>{_cdata(f'<p>{p.question}</p>')}</text>\n"
            body += f"      <answer><text>{_xml_escape(p.answer)}</text></answer>\n"
            body += "    </subquestion>\n"
        return head + body + "  </question>\n"

    # Multiple choice
    single = "true" if q.single else "false"
    body = (
        f"    <single>{single}</single>\n"
        "    <shuffleanswers>true</shuffleanswers>\n"
        "    <answernumbering>abc</answernumbering>\n"
    )
    for o in q.options:
        body += _xml_answer(o.text, o.fraction, o.feedback)
    return head + body + "  </question>\n"


def to_xml(questions: List[Question]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"]
    for q in questions:
        parts.append(_xml_question(q))
    parts.append("</quiz>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Aiken (multiple-choice / true-false only)
# --------------------------------------------------------------------------- #

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def to_aiken(questions: List[Question]) -> Tuple[str, List[str]]:
    """Return ``(content, skipped)``. ``skipped`` lists questions Aiken cannot hold."""
    out: List[str] = []
    skipped: List[str] = []

    for q in questions:
        if q.qtype == QTYPE_TRUEFALSE:
            is_true = (q.correct or "").lower().startswith("t")
            out.append(q.text)
            out.append("A. True")
            out.append("B. False")
            out.append(f"ANSWER: {'A' if is_true else 'B'}")
            out.append("")
            continue

        if q.qtype == QTYPE_MULTICHOICE and q.single and len(q.options) <= 26:
            out.append(q.text)
            correct_letter = None
            best_fraction = -1.0
            for i, o in enumerate(q.options):
                out.append(f"{_LETTERS[i]}. {o.text}")
                if o.fraction > best_fraction:
                    best_fraction = o.fraction
                    correct_letter = _LETTERS[i]
            out.append(f"ANSWER: {correct_letter or 'A'}")
            out.append("")
            continue

        label = q.display_name(40)
        skipped.append(f"Q{q.number} ({q.qtype}): {label}")

    content = "\n".join(out).rstrip() + "\n" if out else ""
    if skipped:
        notice = (
            "// Aiken supports only single-answer Multiple Choice and True/False.\n"
            f"// {len(skipped)} question(s) could not be included — use GIFT or XML for those:\n"
        )
        for s in skipped:
            notice += f"//   - {s}\n"
        content = notice + "\n" + content

    return content, skipped


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #

def serialize_all(questions: List[Question]) -> dict:
    """Produce all three formats at once for the preview/download UI."""
    aiken, aiken_skipped = to_aiken(questions)
    return {
        "gift": to_gift(questions),
        "xml": to_xml(questions),
        "aiken": aiken,
        "aiken_skipped": aiken_skipped,
    }
