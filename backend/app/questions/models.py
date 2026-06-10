"""Internal question model shared by the parser, AI normalizer, and serializers.

Everything in this package speaks in terms of :class:`Question`. The rules
parser and the Claude normalizer both produce ``Question`` objects, and all
three serializers (GIFT / XML / Aiken) consume them, so the output is identical
no matter how a question was understood.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Canonical question types — these map directly onto Moodle's importable types.
QTYPE_MULTICHOICE = "multichoice"      # single or multiple answer (fractions decide)
QTYPE_TRUEFALSE = "truefalse"
QTYPE_SHORTANSWER = "shortanswer"
QTYPE_ESSAY = "essay"
QTYPE_MATCHING = "matching"
QTYPE_NUMERICAL = "numerical"

ALL_QTYPES = {
    QTYPE_MULTICHOICE,
    QTYPE_TRUEFALSE,
    QTYPE_SHORTANSWER,
    QTYPE_ESSAY,
    QTYPE_MATCHING,
    QTYPE_NUMERICAL,
}

# Human-friendly labels for the preview UI.
QTYPE_LABELS = {
    QTYPE_MULTICHOICE: "Multiple Choice",
    QTYPE_TRUEFALSE: "True/False",
    QTYPE_SHORTANSWER: "Short Answer",
    QTYPE_ESSAY: "Essay",
    QTYPE_MATCHING: "Matching",
    QTYPE_NUMERICAL: "Numerical",
}


@dataclass
class Option:
    """A single multiple-choice option.

    ``fraction`` is a percentage of the question's grade: ``100`` for a fully
    correct single answer, ``0`` for wrong, and values in between (or negative)
    for partial-credit / multi-answer questions.
    """

    text: str
    fraction: float = 0.0
    feedback: str = ""

    @property
    def is_correct(self) -> bool:
        return self.fraction > 0

    def to_dict(self) -> dict:
        return {"text": self.text, "fraction": self.fraction, "feedback": self.feedback}


@dataclass
class Answer:
    """An accepted answer for short-answer or numerical questions."""

    text: str
    fraction: float = 100.0
    tolerance: Optional[float] = None  # numerical only

    def to_dict(self) -> dict:
        d = {"text": self.text, "fraction": self.fraction}
        if self.tolerance is not None:
            d["tolerance"] = self.tolerance
        return d


@dataclass
class Pair:
    """A matching sub-question / answer pair."""

    question: str
    answer: str

    def to_dict(self) -> dict:
        return {"question": self.question, "answer": self.answer}


@dataclass
class Question:
    """A single parsed question, type-agnostic container."""

    qtype: str
    text: str
    number: int = 0
    name: str = ""                       # short title; derived from text if blank
    single: bool = True                  # multichoice: True = one answer only
    options: List[Option] = field(default_factory=list)
    answers: List[Answer] = field(default_factory=list)
    pairs: List[Pair] = field(default_factory=list)
    correct: Optional[str] = None        # truefalse: "true" / "false"
    feedback: str = ""                   # general feedback shown after answering
    warnings: List[str] = field(default_factory=list)  # per-question review notes
    source_text: str = ""                # the raw block this came from

    def display_name(self, max_len: int = 80) -> str:
        """A short, safe question name for the GIFT/XML ``name`` field."""
        base = (self.name or self.text or "Question").strip()
        # Collapse whitespace/newlines so names stay on one line.
        base = " ".join(base.split())
        if len(base) > max_len:
            base = base[: max_len - 1].rstrip() + "…"
        return base or "Question"

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "qtype": self.qtype,
            "type_label": QTYPE_LABELS.get(self.qtype, self.qtype),
            "text": self.text,
            "name": self.display_name(),
            "single": self.single,
            "options": [o.to_dict() for o in self.options],
            "answers": [a.to_dict() for a in self.answers],
            "pairs": [p.to_dict() for p in self.pairs],
            "correct": self.correct,
            "feedback": self.feedback,
            "warnings": self.warnings,
        }


@dataclass
class ParseResult:
    """The outcome of parsing a block of pasted text."""

    questions: List[Question] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)        # global notes
    unparsed: List[dict] = field(default_factory=list)       # {"text", "reason"}
    used_ai: bool = False

    def summary(self) -> dict:
        by_type: dict = {}
        review = 0
        for q in self.questions:
            label = QTYPE_LABELS.get(q.qtype, q.qtype)
            by_type[label] = by_type.get(label, 0) + 1
            if q.warnings:
                review += 1
        return {
            "total": len(self.questions),
            "by_type": by_type,
            "needs_review": review,
            "unparsed": len(self.unparsed),
        }

    def to_dict(self) -> dict:
        return {
            "questions": [q.to_dict() for q in self.questions],
            "warnings": self.warnings,
            "unparsed": self.unparsed,
            "used_ai": self.used_ai,
            "summary": self.summary(),
        }
