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


def _renumber(questions) -> None:
    for i, q in enumerate(questions, start=1):
        q.number = i


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

        else:  # auto — deterministic first, Claude only for the leftovers
            result = parse_text(text)
            if result.unparsed and have_ai:
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
            elif result.unparsed and not have_ai:
                # Auto mode degrades gracefully when no key is configured.
                result.warnings.append(
                    f"{len(result.unparsed)} block(s) couldn't be parsed by the rules engine. "
                    "AI cleanup is unavailable (no Anthropic API key configured) — reformat "
                    "those blocks, or configure a key to let Claude interpret them."
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
