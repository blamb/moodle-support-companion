"""Forgiving, deterministic parser for pasted quiz questions.

Design goals, in priority order:

1. **Never drop silently.** Anything that looks like a question but can't be
   fully understood is either kept *with a warning* or surfaced in ``unparsed``
   with a reason. The original tool's biggest failing was discarding questions
   that had no recognised answer key.
2. **Accept the messy realities of copy-paste.** Smart quotes, Word bold as a
   "this is the correct answer" signal, asterisk markers, many answer-key
   phrasings (``Answer:``, ``Ans:``, ``Key:``, ``Correct:``), ``A)``/``A.``/
   ``(A)`` option styles, and unnumbered blocks separated by blank lines.
3. **Stay explicit where the author was explicit.** ``SHORT:``, ``ESSAY:``,
   ``MATCH:``, ``NUM:`` / ``NUMERICAL:`` prefixes always win.

For genuinely unstructured input (e.g. a whole Word document pasted as prose),
the Claude normalizer in :mod:`ai_normalizer` is the right tool — this parser
will report the leftovers so the caller can escalate them.
"""

from __future__ import annotations

import re
from typing import List, Optional

from .models import (
    Answer,
    Option,
    Pair,
    ParseResult,
    Question,
    QTYPE_ESSAY,
    QTYPE_MATCHING,
    QTYPE_MULTICHOICE,
    QTYPE_NUMERICAL,
    QTYPE_SHORTANSWER,
    QTYPE_TRUEFALSE,
)

# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #

_SMART_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-",
    "…": "...", " ": " ", "​": "",
    "\t": "    ",
}


def _normalize(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    for bad, good in _SMART_MAP.items():
        text = text.replace(bad, good)
    return text


# --------------------------------------------------------------------------- #
# Line-level patterns
# --------------------------------------------------------------------------- #

# Question start: "1.", "1)", "Q1.", "Question 1:", "1 -"
RE_QSTART = re.compile(r"^(?:Q(?:uestion)?\s*)?(\d+)\s*[\.\)\:\-]\s+(.*)$", re.IGNORECASE)

# Type-prefixed question: "SHORT: ...", "ESSAY: ...", etc.
RE_TYPED = re.compile(
    r"^(SHORT(?:ANSWER)?|ESSAY|MATCH(?:ING)?|NUM(?:ERICAL)?|MC|MULTI(?:PLE)?|TF|TRUEFALSE)\s*:\s*(.*)$",
    re.IGNORECASE,
)

# A lettered option line: optional leading correctness marker, a letter,
# separator, text, optional trailing percentage. Captures: marker, letter, body.
RE_OPTION = re.compile(
    r"^\s*(?P<lead>[\*\+✓✔☑>\-]+\s*)?"      # leading marker(s)
    r"\(?(?P<letter>[A-Za-z])[\.\)\:]"                       # A) A. A: (A)
    r"\s*(?P<body>.+?)\s*$"
)

# A bullet option with no letter, e.g. "* Red", "- Coal", "• Wind", "✓ Solar".
# A "*", "+", or check mark also signals the correct answer; "-"/"•" are neutral.
RE_BULLET = re.compile(r"^\s*(?P<lead>[\*\+✓✔☑•\-])\s+(?P<body>.+?)\s*$")

# Trailing percentage on an option, e.g. "Solar 25%" or "Coal -50%".
RE_TRAILING_PCT = re.compile(r"^(?P<text>.*?)\s+(?P<pct>[-+]?\d+(?:\.\d+)?)\s*%\s*$")

# Inline "this is correct" markers at the end of an option.
RE_TRAILING_CORRECT = re.compile(
    r"\s*(?:\(\s*correct\s*\)|\[\s*correct\s*\]|✓|✔|\*+|<<+|\(ans(?:wer)?\))\s*$",
    re.IGNORECASE,
)

# Answer-key lines: "Answer: B", "Correct answer: B", "Ans: B", "Key: B",
# "Correct: B". The captured group may be a letter or free text.
RE_ANSWERKEY = re.compile(
    r"^\s*(?:correct\s*answer|correct|answer|ans|key|solution)\s*[:\-=]\s*(?P<val>.+?)\s*$",
    re.IGNORECASE,
)

# Feedback / rationale line attached to a question.
RE_FEEDBACK = re.compile(
    r"^\s*(?:feedback|rationale|explanation|note)\s*[:\-]\s*(?P<val>.+?)\s*$",
    re.IGNORECASE,
)

# Short-answer accepted answer: "= Paris" or "ANSWER: Paris".
RE_SA_ANSWER = re.compile(r"^\s*(?:=|ANSWER:|ACCEPT:)\s*(?P<val>.+?)\s*$", re.IGNORECASE)

# Matching pair: "France -> Paris" or "France => Paris" or "France : Paris".
RE_PAIR = re.compile(r"^\s*(?P<q>.+?)\s*(?:->|=>|:|\t+|\s{2,})\s*(?P<a>.+?)\s*$")

# Markdown / HTML bold wrapping a whole string.
RE_BOLD = re.compile(r"^\s*(?:\*\*|__|<b>|<strong>)(.+?)(?:\*\*|__|</b>|</strong>)\s*$",
                     re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Working accumulator
# --------------------------------------------------------------------------- #

class _Acc:
    """Mutable scratch state for the question currently being assembled."""

    def __init__(self, number: int, text: str, qtype: str = QTYPE_MULTICHOICE):
        self.number = number
        self.text_lines: List[str] = [text] if text else []
        self.qtype = qtype
        self.raw_lines: List[str] = []
        # multichoice
        self.options: List[dict] = []          # {letter, text, fraction?, marked}
        self.answer_keys: List[str] = []        # raw values from answer-key lines
        # short answer / numerical
        self.answers: List[str] = []
        # matching
        self.pairs: List[Pair] = []
        self.feedback: str = ""

    @property
    def stem(self) -> str:
        return " ".join(" ".join(self.text_lines).split())

    @property
    def raw(self) -> str:
        return "\n".join(self.raw_lines).strip()


# --------------------------------------------------------------------------- #
# Detecting a correct-answer marker on an option line
# --------------------------------------------------------------------------- #

def _extract_option(line: str) -> Optional[dict]:
    """Parse one option line into {letter, text, fraction?, marked}.

    ``letter`` is ``None`` for bullet options with no letter; the caller assigns
    a synthetic letter by position.
    """
    m = RE_OPTION.match(line)
    if m:
        letter = m.group("letter").upper()
        body = m.group("body").strip()
        marked = bool(m.group("lead"))  # leading * / + / ✓ / > etc.
    else:
        b = RE_BULLET.match(line)
        if not b:
            return None
        letter = None
        body = b.group("body").strip()
        marked = b.group("lead") in "*+✓✔☑"

    fraction = None

    # Trailing percentage → partial credit.
    pct = RE_TRAILING_PCT.match(body)
    if pct:
        body = pct.group("text").strip()
        fraction = float(pct.group("pct"))

    # Bold-wrapped body is a "correct" signal (Word habit), then unwrap it.
    bold = RE_BOLD.match(body)
    if bold:
        body = bold.group(1).strip()
        marked = True

    # Trailing "(correct)" / ✓ / asterisk markers.
    if RE_TRAILING_CORRECT.search(body):
        body = RE_TRAILING_CORRECT.sub("", body).strip()
        marked = True

    return {"letter": letter, "text": body, "fraction": fraction, "marked": marked}


# --------------------------------------------------------------------------- #
# Finalizing an accumulator into a Question
# --------------------------------------------------------------------------- #

def _looks_like_truefalse(opts: List[dict]) -> bool:
    if len(opts) != 2:
        return False
    texts = {o["text"].strip().lower() for o in opts}
    return texts <= {"true", "false", "t", "f"} and len(texts) == 2


def _finalize(acc: _Acc) -> tuple[Optional[Question], Optional[str]]:
    """Turn an accumulator into a Question, or return (None, reason) if unusable."""
    stem = acc.stem
    qtype = acc.qtype

    # ---- Explicitly typed questions -------------------------------------- #
    if qtype == QTYPE_ESSAY:
        if not stem:
            return None, "Essay question had no prompt text."
        return Question(qtype=QTYPE_ESSAY, text=stem, number=acc.number,
                        feedback=acc.feedback, source_text=acc.raw), None

    if qtype == QTYPE_SHORTANSWER:
        if not acc.answers:
            return None, "Short-answer question had no accepted answers (use '=' or 'ANSWER:')."
        return Question(
            qtype=QTYPE_SHORTANSWER, text=stem, number=acc.number,
            answers=[Answer(text=a, fraction=100) for a in acc.answers],
            feedback=acc.feedback, source_text=acc.raw,
        ), None

    if qtype == QTYPE_NUMERICAL:
        warns: List[str] = []
        answers: List[Answer] = []
        for a in acc.answers:
            num, tol = _split_numeric(a)
            if num is None:
                warns.append(f"Couldn't read '{a}' as a number; left as-is for review.")
                answers.append(Answer(text=a, fraction=100, tolerance=0))
            else:
                answers.append(Answer(text=num, fraction=100, tolerance=tol))
        if not answers:
            return None, "Numerical question had no answer value."
        return Question(qtype=QTYPE_NUMERICAL, text=stem, number=acc.number,
                        answers=answers, warnings=warns, feedback=acc.feedback,
                        source_text=acc.raw), None

    if qtype == QTYPE_MATCHING:
        if len(acc.pairs) < 2:
            return None, "Matching question needs at least two 'Item -> Match' pairs."
        return Question(qtype=QTYPE_MATCHING, text=stem, number=acc.number,
                        pairs=acc.pairs, feedback=acc.feedback,
                        source_text=acc.raw), None

    # ---- Multiple choice (the common, messy case) ------------------------ #
    if not acc.options:
        # No options at all. Could be an essay-style prompt or junk.
        if not stem:
            return None, "Empty block."
        return None, "Looks like a question stem but has no options or answer."

    warns: List[str] = []

    # True/False shortcut.
    if _looks_like_truefalse(acc.options):
        correct = _resolve_correct_letter(acc)
        if correct is None:
            warns.append("True/False answer not marked — defaulted to True. Please verify.")
            correct_text = "true"
        else:
            opt = next((o for o in acc.options if o["letter"] == correct), None)
            correct_text = (opt["text"].lower() if opt else "true")
            correct_text = "true" if correct_text.startswith("t") else "false"
        return Question(qtype=QTYPE_TRUEFALSE, text=stem, number=acc.number,
                        correct=correct_text, warnings=warns,
                        feedback=acc.feedback, source_text=acc.raw), None

    has_pct = any(o["fraction"] is not None for o in acc.options)
    marked = [o for o in acc.options if o["marked"]]
    correct_letter = _resolve_correct_letter(acc)

    options: List[Option] = []

    if has_pct:
        # Partial-credit / multi-answer: trust the percentages.
        for o in acc.options:
            frac = o["fraction"] if o["fraction"] is not None else 0.0
            options.append(Option(text=o["text"], fraction=frac))
        single = sum(1 for o in options if o.fraction > 0) <= 1
        missing = [o for o in acc.options if o["fraction"] is None]
        if missing:
            warns.append("Some options had no percentage; treated as 0%. Please verify.")
        return Question(qtype=QTYPE_MULTICHOICE, text=stem, number=acc.number,
                        single=single, options=options, warnings=warns,
                        feedback=acc.feedback, source_text=acc.raw), None

    if len(marked) > 1:
        # Several options flagged correct → multiple-answer question, split evenly.
        share = round(100.0 / len(marked), 5)
        for o in acc.options:
            options.append(Option(text=o["text"], fraction=share if o["marked"] else -share))
        warns.append("Multiple correct answers detected — set up as a multiple-response "
                     "question with even credit. Please verify the weighting.")
        return Question(qtype=QTYPE_MULTICHOICE, text=stem, number=acc.number,
                        single=False, options=options, warnings=warns,
                        feedback=acc.feedback, source_text=acc.raw), None

    # Single-answer multiple choice.
    chosen = correct_letter
    if chosen is None and len(marked) == 1:
        chosen = marked[0]["letter"]
    if chosen is None:
        # KEY DIFFERENCE FROM THE ORIGINAL TOOL: keep the question, flag it,
        # rather than silently discarding it.
        chosen = acc.options[0]["letter"]
        warns.append("No correct answer detected — defaulted to the first option. "
                     "Please mark the right answer before importing.")
    for o in acc.options:
        options.append(Option(text=o["text"], fraction=100.0 if o["letter"] == chosen else 0.0))

    return Question(qtype=QTYPE_MULTICHOICE, text=stem, number=acc.number,
                    single=True, options=options, warnings=warns,
                    feedback=acc.feedback, source_text=acc.raw), None


def _resolve_correct_letter(acc: _Acc) -> Optional[str]:
    """Work out which option letter the answer-key lines point at."""
    for raw in acc.answer_keys:
        val = raw.strip()
        # A bare letter like "B" or "(B)".
        lm = re.match(r"^\(?([A-Za-z])\)?$", val)
        if lm:
            return lm.group(1).upper()
        # Letter followed by text, "B) Paris" or "B. Paris".
        lm = re.match(r"^\(?([A-Za-z])[\.\)\:]", val)
        if lm:
            return lm.group(1).upper()
        # Free text matching an option's text.
        for o in acc.options:
            if o["text"].strip().lower() == val.lower():
                return o["letter"]
    return None


def _split_numeric(text: str) -> tuple[Optional[str], float]:
    """Parse "42", "42 +/- 0.5", "3.14:0.01" → (value, tolerance)."""
    t = text.strip()
    m = re.match(r"^([-+]?\d+(?:\.\d+)?)\s*(?:(?:\+/-|±|:)\s*([-+]?\d+(?:\.\d+)?))?$", t)
    if not m:
        return None, 0.0
    value = m.group(1)
    tol = float(m.group(2)) if m.group(2) else 0.0
    return value, tol


_TYPE_PREFIX_MAP = {
    "SHORT": QTYPE_SHORTANSWER, "SHORTANSWER": QTYPE_SHORTANSWER,
    "ESSAY": QTYPE_ESSAY,
    "MATCH": QTYPE_MATCHING, "MATCHING": QTYPE_MATCHING,
    "NUM": QTYPE_NUMERICAL, "NUMERICAL": QTYPE_NUMERICAL,
    "MC": QTYPE_MULTICHOICE, "MULTI": QTYPE_MULTICHOICE, "MULTIPLE": QTYPE_MULTICHOICE,
    "TF": QTYPE_TRUEFALSE, "TRUEFALSE": QTYPE_TRUEFALSE,
}


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def parse_text(raw: str) -> ParseResult:
    """Parse pasted text into questions, reporting anything it couldn't use."""
    result = ParseResult()
    text = _normalize(raw or "")
    if not text.strip():
        return result

    lines = text.split("\n")
    acc: Optional[_Acc] = None
    qnum = 0

    def flush():
        nonlocal acc
        if acc is None:
            return
        q, reason = _finalize(acc)
        if q is not None:
            result.questions.append(q)
        elif acc.raw:
            result.unparsed.append({"text": acc.raw, "reason": reason or "Could not parse."})
        acc = None

    for rawline in lines:
        line = rawline.rstrip()
        stripped = line.strip()

        if not stripped:
            if acc is not None:
                acc.raw_lines.append(rawline)
            continue

        # 1. Type-prefixed start (SHORT:, ESSAY:, MATCH:, NUM:, MC:, TF:)
        mt = RE_TYPED.match(stripped)
        if mt:
            flush()
            qnum += 1
            key = mt.group(1).upper()
            qtype = _TYPE_PREFIX_MAP.get(key, QTYPE_MULTICHOICE)
            acc = _Acc(qnum, mt.group(2).strip(), qtype)
            acc.raw_lines.append(rawline)
            continue

        # 2. Numbered question start ("1.", "Q1:", ...)
        mq = RE_QSTART.match(stripped)
        if mq and not _extract_option(stripped):
            flush()
            qnum += 1
            acc = _Acc(qnum, mq.group(2).strip(), QTYPE_MULTICHOICE)
            acc.raw_lines.append(rawline)
            continue

        # Everything below needs an open question.
        if acc is None:
            # Unnumbered first line — open a new MC question with this as stem.
            qnum += 1
            acc = _Acc(qnum, stripped, QTYPE_MULTICHOICE)
            acc.raw_lines.append(rawline)
            continue

        # 3. Type-specific continuation lines
        if acc.qtype == QTYPE_MATCHING:
            mp = RE_PAIR.match(stripped)
            if mp:
                acc.raw_lines.append(rawline)
                acc.pairs.append(Pair(question=mp.group("q").strip(),
                                      answer=mp.group("a").strip()))
                continue

        if acc.qtype in (QTYPE_SHORTANSWER, QTYPE_NUMERICAL):
            ma = RE_SA_ANSWER.match(stripped)
            if ma:
                acc.raw_lines.append(rawline)
                acc.answers.append(ma.group("val").strip())
                continue

        # 4. Feedback / rationale (any type)
        mf = RE_FEEDBACK.match(stripped)
        if mf:
            acc.raw_lines.append(rawline)
            acc.feedback = (acc.feedback + " " + mf.group("val").strip()).strip()
            continue

        # 5. Answer-key line (multiple choice)
        mak = RE_ANSWERKEY.match(stripped)
        if mak and acc.qtype == QTYPE_MULTICHOICE:
            acc.raw_lines.append(rawline)
            acc.answer_keys.append(mak.group("val").strip())
            continue

        # 6. Option line (multiple choice)
        if acc.qtype == QTYPE_MULTICHOICE:
            opt = _extract_option(stripped)
            if opt:
                # Bullet options carry no letter — assign one by position.
                if opt["letter"] is None:
                    opt["letter"] = chr(ord("A") + len(acc.options))
                acc.raw_lines.append(rawline)
                acc.options.append(opt)
                continue

            # Non-option, non-key line while we already have options →
            # likely the stem of the *next* (unnumbered) question.
            if acc.options:
                flush()
                qnum += 1
                acc = _Acc(qnum, stripped, QTYPE_MULTICHOICE)
                acc.raw_lines.append(rawline)
                continue

            # Otherwise treat it as a continuation of the stem.
            acc.raw_lines.append(rawline)
            acc.text_lines.append(stripped)
            continue

        # Fallback: extend the stem.
        acc.raw_lines.append(rawline)
        acc.text_lines.append(stripped)

    flush()
    return result
