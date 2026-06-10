"""Extract question text from an uploaded .docx (or plain .txt) file.

Word is the format instructors actually use, and a naive ``paragraph.text``
extraction loses two things that matter a lot for quiz questions:

1. **List numbering.** Word stores "1." / "A)" in the numbering definition, not
   the paragraph text, so a numbered question list comes out with no numbers and
   becomes unparseable. We reconstruct numbering from each paragraph's list
   level: top-level items get ``1. 2. 3.`` (questions), nested items get
   ``A) B) C)`` (options).
2. **Bold.** Instructors overwhelmingly mark the correct option by bolding it.
   We wrap bold runs inside option lines in ``**...**`` so the rules parser's
   existing bold-means-correct detection fires.

The result is plain text fed straight into :func:`parser.parse_text` (or the AI
normalizer). It won't be perfect for every Word layout — tables and unusual
structures still benefit from Smart/AI mode — but it makes the common cases work.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ALREADY_PREFIXED = re.compile(r"^\s*\(?[A-Za-z0-9][\.\)]")


_STYLE_LIST_NAME = re.compile(r"List\s+(Number|Bullet)(?:\s+(\d+))?", re.IGNORECASE)


def _numpr_level(pPr) -> Optional[int]:
    """Read the ilvl from a ``<w:pPr>`` element's numbering, if present."""
    if pPr is None or pPr.numPr is None:
        return None
    ilvl = pPr.numPr.ilvl
    return int(ilvl.val) if ilvl is not None and ilvl.val is not None else 0


def _list_info(paragraph) -> Optional[tuple]:
    """Return ``(kind, level)`` for a list paragraph, or None if it isn't one.

    ``kind`` is ``"number"`` or ``"bullet"``; ``level`` is the 0-based nesting
    depth. The built-in style name is the most reliable nesting signal in real
    instructor documents ("List Number" = questions, "List Number 2" = options),
    so it's checked first; direct/inherited numbering covers toolbar lists.
    """
    # 1. Built-in list style name — clearest signal of kind AND depth.
    try:
        name = (paragraph.style.name if paragraph.style else "") or ""
        m = _STYLE_LIST_NAME.search(name)
        if m:
            kind = m.group(1).lower()
            depth = int(m.group(2)) if m.group(2) else 1
            return (kind, depth - 1)
    except Exception:
        pass

    # 2. Direct numbering on the paragraph (toolbar numbered/bulleted list).
    try:
        lvl = _numpr_level(paragraph._p.pPr)
        if lvl is not None:
            return ("number", lvl)
    except Exception:
        pass

    # 3. Numbering inherited from the paragraph's style chain.
    try:
        style = paragraph.style
        seen = 0
        while style is not None and seen < 10:
            seen += 1
            el = getattr(style, "element", None)
            pPr = getattr(el, "pPr", None) if el is not None else None
            lvl = _numpr_level(pPr)
            if lvl is not None:
                return ("number", lvl)
            style = getattr(style, "base_style", None)
    except Exception:
        pass

    return None


def _runs_text(paragraph, preserve_bold: bool) -> str:
    """Concatenate a paragraph's runs, optionally wrapping bold runs in ``**``."""
    if not preserve_bold:
        return paragraph.text
    parts: List[str] = []
    for run in paragraph.runs:
        t = run.text
        if t and run.bold:
            # Keep surrounding whitespace outside the markers.
            lead = t[: len(t) - len(t.lstrip())]
            trail = t[len(t.rstrip()):]
            core = t.strip()
            t = f"{lead}**{core}**{trail}" if core else t
        parts.append(t)
    return "".join(parts) or paragraph.text


def _iter_blocks(document):
    """Yield paragraphs and tables in document order."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def extract_docx(path: str) -> str:
    """Extract question-friendly plain text from a .docx file."""
    from docx import Document as DocxDocument
    from docx.table import Table

    document = DocxDocument(path)
    lines: List[str] = []
    counters: dict = {}  # list level -> running count

    for block in _iter_blocks(document):
        if isinstance(block, Table):
            # Flatten each row's cells onto their own lines; blank line between rows.
            for row in block.rows:
                for cell in row.cells:
                    cell_text = "\n".join(p.text for p in cell.paragraphs).strip()
                    if cell_text:
                        lines.append(cell_text)
                lines.append("")
            continue

        para = block
        info = _list_info(para)

        if info is None:
            lines.append(para.text.rstrip())
            continue

        kind, level = info
        # A list item — reconstruct its marker.
        counters[level] = counters.get(level, 0) + 1
        for deeper in [k for k in counters if k > level]:
            counters[deeper] = 0

        if kind == "bullet":
            # Bullets are almost always options; "-" is read as a neutral option
            # and a bold run still flags the correct one.
            text = _runs_text(para, preserve_bold=True).strip()
            prefix = "" if _ALREADY_PREFIXED.match(text) else "- "
        elif level == 0:
            # Top-level numbered item → a question number.
            text = _runs_text(para, preserve_bold=False).strip()
            prefix = "" if _ALREADY_PREFIXED.match(text) else f"{counters[level]}. "
        else:
            # Nested numbered item → a lettered option; preserve bold = correct.
            text = _runs_text(para, preserve_bold=True).strip()
            letter = _LETTERS[(counters[level] - 1) % len(_LETTERS)]
            prefix = "" if _ALREADY_PREFIXED.match(text) else f"{letter}) "

        lines.append(prefix + text)

    # Collapse runs of 3+ blank lines down to a single blank-line separator.
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_file(filename: str, content: bytes) -> str:
    """Extract text from an uploaded question file (.docx or .txt)."""
    name = (filename or "").lower()
    if name.endswith(".txt") or name.endswith(".md"):
        return content.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        import tempfile
        import os

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            return extract_docx(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    raise ValueError("Unsupported file type. Upload a .docx or .txt file.")
