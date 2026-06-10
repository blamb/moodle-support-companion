"""Claude-backed normalizer for genuinely messy question input.

When the deterministic parser can't make sense of pasted text — a whole Word
document dumped as prose, wildly inconsistent answer marking, mixed numbering —
this module asks Claude to read it the way a human would and emit a strict JSON
structure that maps onto our :class:`Question` model.

Crucially, Claude is told to *report its assumptions* (e.g. "Q3 had no marked
answer; I inferred B from the rationale") so the support technologist can verify
before importing. Nothing is invented out of thin air: if a question is
unsalvageable, Claude lists it under ``unparsed`` rather than guessing.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

import anthropic

from ..config import CLAUDE_MODEL
from .models import (
    Answer,
    Option,
    Pair,
    ParseResult,
    Question,
    ALL_QTYPES,
    QTYPE_MULTICHOICE,
)

logger = logging.getLogger(__name__)

# A focused max — question sets are not huge, and this keeps latency/cost sane.
_MAX_TOKENS = 8000

_SYSTEM = """You are a meticulous assistant that converts messy, human-written \
quiz questions into clean structured data for import into Moodle. You work for a \
university Learning Technology team that receives questions from instructors in \
every imaginable format.

Your job: read whatever the instructor pasted and extract every question you can \
identify, normalizing each into the schema below. You are careful and honest:

- NEVER invent a correct answer you are not reasonably sure about. If a question \
  has options but no discernible correct answer, still include it, set no option \
  to fraction 100, and add a warning explaining the answer is unmarked.
- Preserve the instructor's wording. Lightly fix obvious typos only.
- Record every assumption or judgement call you made in the question's \
  "warnings" array (e.g. inferred answer, guessed type, split a run-on question).
- If a block of text is clearly not a question (instructions, a heading, a \
  greeting), put it in the top-level "unparsed" array with a short reason. Do \
  not force it into a question.

Question types (use exactly these strings for "type"):
- "multichoice"  — single OR multiple answer; set "single" true/false. Each \
  option has "text" and "fraction" (100 = fully correct, 0 = wrong, partial \
  values allowed; negative to penalise in multi-answer).
- "truefalse"    — set "correct" to "true" or "false". No options needed.
- "shortanswer"  — "answers": list of {text, fraction} accepted answers.
- "numerical"    — "answers": list of {text (the number as a string), fraction, \
  tolerance (number)}.
- "essay"        — open response; no answer data.
- "matching"     — "pairs": list of {question, answer}.

Output ONLY a single JSON object, no prose, no markdown fences, matching:
{
  "questions": [
    {
      "type": "multichoice|truefalse|shortanswer|numerical|essay|matching",
      "name": "short title (<= 80 chars)",
      "text": "the question stem",
      "single": true,
      "options": [{"text": "...", "fraction": 100}],
      "answers": [{"text": "...", "fraction": 100, "tolerance": 0}],
      "pairs": [{"question": "...", "answer": "..."}],
      "correct": "true",
      "feedback": "",
      "warnings": ["..."]
    }
  ],
  "unparsed": [{"text": "...", "reason": "..."}],
  "notes": "one or two sentences summarising what you did and anything the \
technologist should double-check"
}
Include only the fields relevant to each question's type."""

_USER_TEMPLATE = """Convert the following pasted questions into the JSON schema. \
Extract every question you can, normalize the types, and record your assumptions \
in each question's "warnings". Remember: do not guess correct answers you aren't \
confident about — flag them instead.

<pasted_questions>
{text}
</pasted_questions>"""


def ai_configured() -> bool:
    """True if an Anthropic credential is available.

    The SDK resolves auth lazily and raises a bare ``TypeError`` at call time
    when nothing is configured, so we check up front for a clean error path.
    """
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _strip_json(text: str) -> str:
    """Pull the JSON object out of a model response, tolerating stray fences."""
    t = text.strip()
    if t.startswith("```"):
        # Drop the opening fence (``` or ```json) and the trailing fence.
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start : end + 1]
    return t


def _question_from_dict(d: dict, number: int) -> Optional[Question]:
    qtype = str(d.get("type", "")).strip().lower()
    if qtype not in ALL_QTYPES:
        # Unknown type — best effort: treat as multichoice if it has options.
        qtype = QTYPE_MULTICHOICE if d.get("options") else "essay"

    text = str(d.get("text", "")).strip()
    if not text:
        return None

    warnings = [str(w) for w in (d.get("warnings") or []) if str(w).strip()]

    options = [
        Option(text=str(o.get("text", "")).strip(),
               fraction=float(o.get("fraction", 0) or 0),
               feedback=str(o.get("feedback", "")).strip())
        for o in (d.get("options") or [])
        if str(o.get("text", "")).strip()
    ]

    answers = []
    for a in (d.get("answers") or []):
        atext = str(a.get("text", "")).strip()
        if not atext:
            continue
        tol = a.get("tolerance")
        answers.append(Answer(text=atext,
                              fraction=float(a.get("fraction", 100) or 100),
                              tolerance=float(tol) if tol is not None else None))

    pairs = [
        Pair(question=str(p.get("question", "")).strip(),
             answer=str(p.get("answer", "")).strip())
        for p in (d.get("pairs") or [])
        if str(p.get("question", "")).strip() and str(p.get("answer", "")).strip()
    ]

    correct = d.get("correct")
    correct = str(correct).strip().lower() if correct is not None else None

    return Question(
        qtype=qtype,
        text=text,
        number=number,
        name=str(d.get("name", "")).strip(),
        single=bool(d.get("single", True)),
        options=options,
        answers=answers,
        pairs=pairs,
        correct=correct,
        feedback=str(d.get("feedback", "")).strip(),
        warnings=warnings,
    )


async def normalize_with_ai(text: str, start_number: int = 1) -> ParseResult:
    """Ask Claude to normalize messy ``text`` into a :class:`ParseResult`.

    Raises ``anthropic.APIError`` on API failure and ``ValueError`` if the
    response can't be parsed as the expected JSON — the router maps both to
    clean HTTP errors.
    """
    result = ParseResult(used_ai=True)
    if not text.strip():
        return result

    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _USER_TEMPLATE.format(text=text)}],
    )
    raw = response.content[0].text if response.content else ""

    try:
        data = json.loads(_strip_json(raw))
    except json.JSONDecodeError as e:
        logger.error("AI normalizer returned non-JSON: %s", e)
        raise ValueError("The AI returned an unexpected response. Try again or use rules-only mode.")

    number = start_number
    for qd in data.get("questions", []):
        q = _question_from_dict(qd, number)
        if q is not None:
            result.questions.append(q)
            number += 1

    for u in data.get("unparsed", []):
        if isinstance(u, dict) and u.get("text"):
            result.unparsed.append({"text": str(u["text"]),
                                    "reason": str(u.get("reason", "Not a question."))})

    notes = str(data.get("notes", "")).strip()
    if notes:
        result.warnings.append(notes)

    return result
