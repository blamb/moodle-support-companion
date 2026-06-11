"""Question import API — parse pasted questions and serialize to Moodle formats.

One endpoint does the work: ``POST /api/questions/parse``. It accepts pasted
text and a mode, returns the structured questions (with per-question review
warnings), anything it couldn't parse, and ready-to-download GIFT / XML / Aiken
content so the frontend can offer an instant download without a second request.
"""

from __future__ import annotations

import logging

import anthropic
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ..questions.parser import parse_text
from ..questions.ai_normalizer import normalize_with_ai, ai_configured
from ..questions.serializers import serialize_all
from ..questions.docx_extract import extract_file
from ..questions.models import question_from_dict

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_INPUT_CHARS = 100_000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class ParseRequest(BaseModel):
    text: str = Field(..., description="The pasted questions")
    # "auto"  — rules first, Claude cleans up only what rules couldn't parse
    # "rules" — deterministic parser only (free, fully private)
    # "ai"    — send everything to Claude (best for very messy input)
    mode: str = Field("auto", pattern="^(auto|rules|ai)$")


class SerializeRequest(BaseModel):
    # Accepts the question dicts as returned by /parse, after the user has
    # edited them in the preview (e.g. marked the correct answer).
    questions: list


def _renumber(questions) -> None:
    for i, q in enumerate(questions, start=1):
        q.number = i


# Warnings the rules parser attaches when it found options but couldn't determine
# the correct answer. In Smart mode these trigger a full-text AI pass, because the
# answer is usually elsewhere (a separate answer key, or bold lost on paste).
_MISSING_ANSWER_PREFIXES = ("No correct answer", "True/False answer not marked")


def _missing_answer(question) -> bool:
    return any(w.startswith(_MISSING_ANSWER_PREFIXES) for w in question.warnings)


@router.post("/questions/extract")
async def extract_question_file(file: UploadFile = File(...)):
    """Extract question text from an uploaded .docx or .txt file.

    Returns the extracted plain text for the user to review (and edit) before
    converting. Word numbering is reconstructed and bolded options are preserved
    so the parser can read them; for unusual layouts, Smart/AI mode cleans up.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".docx", ".txt", ".md")):
        raise HTTPException(
            status_code=400,
            detail="Please upload a .docx or .txt file.",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB).")

    try:
        text = extract_file(filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to extract question file")
        raise HTTPException(status_code=500, detail=f"Couldn't read that file: {e}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text found in that file. If it's a scanned PDF or image, "
                   "paste the questions in manually.",
        )

    note = (
        "Extracted from Word — numbering and bold answers were reconstructed where "
        "possible. Review the text below, then convert (Smart mode handles anything "
        "the extraction didn't get quite right)."
        if filename.lower().endswith(".docx")
        else None
    )
    return {"text": text, "note": note, "filename": filename}


@router.post("/questions/parse")
async def parse_questions(request: ParseRequest):
    """Parse pasted questions into Moodle-importable formats.

    Returns structured questions, review warnings, unparsed leftovers, and the
    serialized GIFT/XML/Aiken content.
    """
    text = request.text or ""
    if not text.strip():
        raise HTTPException(status_code=400, detail="No question text provided.")
    if len(text) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Input too large ({len(text):,} chars; max {MAX_INPUT_CHARS:,}). "
                   "Split it into smaller batches.",
        )

    mode = request.mode
    have_ai = ai_configured()

    try:
        if mode == "ai":
            if not have_ai:
                raise HTTPException(
                    status_code=503,
                    detail="AI cleanup is unavailable (no Anthropic API key configured). "
                           "Use rules-only mode for now.",
                )
            result = await normalize_with_ai(text)

        elif mode == "rules":
            result = parse_text(text)

        else:  # auto — deterministic first, escalate to Claude when needed
            result = parse_text(text)
            missing_answers = any(_missing_answer(q) for q in result.questions)

            if have_ai and missing_answers:
                # Rules parsed the questions but couldn't find the correct answer(s)
                # for some — the marking is non-standard (a separate answer key, or
                # bold lost on paste). A full-text AI pass can cross-reference the
                # whole document the way a person would.
                try:
                    ai_result = await normalize_with_ai(text)
                    # Guard against the AI dropping most of the set; only adopt its
                    # result if it found a comparable number of questions.
                    if ai_result.questions and len(ai_result.questions) >= max(
                        1, len(result.questions) // 2
                    ):
                        result = ai_result
                        result.used_ai = True
                    else:
                        result.warnings.append(
                            "Some answers weren't detected and AI couldn't confidently "
                            "re-read them — showing the rules result. Click the correct "
                            "option on any flagged question to fix it."
                        )
                except (anthropic.AnthropicError, ValueError) as e:
                    result.warnings.append(
                        f"Tried to recover missing answers with AI but it failed: {e}. "
                        "Click the correct option on any flagged question to fix it."
                    )

            elif have_ai and result.unparsed:
                # Only unparsed leftovers — a cheap, targeted pass on those blocks.
                leftover = "\n\n".join(u["text"] for u in result.unparsed)
                try:
                    ai_result = await normalize_with_ai(
                        leftover, start_number=len(result.questions) + 1
                    )
                    result.questions.extend(ai_result.questions)
                    result.unparsed = ai_result.unparsed
                    result.warnings.extend(ai_result.warnings)
                    result.used_ai = True
                except (anthropic.AnthropicError, ValueError) as e:
                    result.warnings.append(
                        f"Couldn't AI-clean {len(result.unparsed)} leftover block(s): {e}"
                    )

            elif not have_ai and (result.unparsed or missing_answers):
                # Auto mode degrades gracefully when no key is configured.
                result.warnings.append(
                    "Some questions are missing a correct answer or couldn't be parsed, and "
                    "AI cleanup is unavailable (no Anthropic API key configured). Click the "
                    "correct option in the preview to set answers, or configure a key."
                )

    except HTTPException:
        raise
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=503,
            detail="AI cleanup is unavailable (Anthropic API key invalid). Use rules-only mode.",
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("Question parse failed")
        raise HTTPException(status_code=500, detail=f"Failed to parse questions: {e}")

    _renumber(result.questions)

    payload = result.to_dict()
    payload["exports"] = serialize_all(result.questions)
    return payload


@router.post("/questions/serialize")
async def serialize_questions(request: SerializeRequest):
    """Re-generate the GIFT/XML/Aiken files from (possibly edited) questions.

    Called when the user fixes a question in the preview — e.g. clicks the
    correct answer on one the parser couldn't determine — so the downloaded
    file reflects their corrections.
    """
    questions = []
    for i, d in enumerate(request.questions, start=1):
        if not isinstance(d, dict):
            continue
        q = question_from_dict(d, i)
        if q is not None:
            questions.append(q)

    if not questions:
        raise HTTPException(status_code=400, detail="No valid questions to serialize.")

    return {"exports": serialize_all(questions)}
