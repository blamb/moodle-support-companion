"""Activity suggestion API — AI-tailored Moodle activity ideas for objectives.

The Activities tab has a fast, offline Bloom's-verb map (handled entirely in the
frontend). This endpoint powers its optional **AI ideas** mode: given learning
objectives and a little course context, Claude suggests Moodle activities that
genuinely fit — deliberately surfacing effective-but-under-used options, since
instructors tend to over-rely on Quiz / Assignment / Forum — each with a
concrete, course-specific way to use it.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import CLAUDE_MODEL
from ..questions.ai_normalizer import ai_configured

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_TOKENS = 4000
_MAX_OBJECTIVES = 12

# The palette of activities available in TRU's Moodle, so suggestions stay
# actionable rather than generic. H5P and Kaltura are the high-interactivity ones
# instructors most often overlook.
_PALETTE = (
    "Assignment; Forum (standard / Q&A / single-discussion); Quiz (multiple choice, "
    "matching, short answer, numerical, calculated, essay); Lesson (branching); "
    "Workshop (peer assessment & self-assessment); Database (student-built collections); "
    "Glossary (collaborative); Wiki; Choice / Group choice; Feedback; Survey; Chat; "
    "Attendance; Scheduler; PDF Annotation; SCORM; Kaltura Media Assignment (student "
    "video/audio); H5P — Interactive Video, Branching Scenario, Course Presentation, "
    "Drag and Drop, Image Hotspots, Dialog Cards, Memory Game"
)

_SYSTEM = f"""You are an instructional designer on a university Learning Technology \
team (Thompson Rivers University). Instructors here tend to over-rely on three \
activities: Quiz, Assignment, and Forum. Your job is to broaden their toolkit.

Given a learning objective (and optional course context), suggest Moodle \
activities that genuinely fit the cognitive work the objective demands. \
Deliberately include effective but UNDER-USED options when they fit — but never \
suggest a tool that doesn't actually suit the objective just for novelty.

Only suggest from this palette of tools available in TRU's Moodle:
{_PALETTE}

For each suggestion give:
- "activity": the tool name (use the palette wording; include the H5P/Quiz subtype \
in parentheses where relevant).
- "why": one sentence on why it fits THIS objective's thinking skill.
- "how": a concrete, course-specific way to use it for this objective (2–3 \
sentences, referencing the subject matter, not generic setup steps).
- "underused": true if this is one of the less-common options you're nudging them \
toward (i.e. not a plain Quiz/Assignment/Forum), else false.

Give 3–4 suggestions per objective, ordered best-fit first, with at least one \
"underused" option per objective when a good one exists.

Output ONLY a single JSON object, no prose or markdown fences:
{{
  "suggestions": [
    {{"objective": "...", "ideas": [
      {{"activity": "...", "why": "...", "how": "...", "underused": true}}
    ]}}
  ],
  "note": "one short sentence of overall guidance for the instructor"
}}"""


class SuggestRequest(BaseModel):
    objectives: List[str] = Field(..., description="Learning objectives")
    course_name: Optional[str] = ""
    course_level: Optional[str] = ""
    course_area: Optional[str] = ""


def _strip_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end > start else t


@router.post("/activities/suggest")
async def suggest_activities(request: SuggestRequest):
    """Suggest tailored Moodle activities for a set of learning objectives."""
    objectives = [o.strip() for o in (request.objectives or []) if o.strip()]
    if not objectives:
        raise HTTPException(status_code=400, detail="Enter at least one learning objective.")
    if len(objectives) > _MAX_OBJECTIVES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many objectives ({len(objectives)}; max {_MAX_OBJECTIVES}). "
                   "Run them in smaller batches.",
        )
    if not ai_configured():
        raise HTTPException(
            status_code=503,
            detail="AI ideas are unavailable (no Anthropic API key configured). "
                   "Use the Bloom's-map mode for instant suggestions.",
        )

    context_bits = []
    if request.course_name:
        context_bits.append(f"Course: {request.course_name}")
    if request.course_level:
        context_bits.append(f"Level: {request.course_level}")
    if request.course_area:
        context_bits.append(f"Area: {request.course_area}")
    context = ("\n".join(context_bits) + "\n\n") if context_bits else ""

    numbered = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(objectives))
    user_msg = (
        f"{context}Suggest tailored Moodle activities for these learning objectives:\n\n{numbered}"
    )

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text if response.content else ""
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=503, detail="AI ideas unavailable (API key invalid).")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    except anthropic.AnthropicError:
        raise HTTPException(
            status_code=503,
            detail="AI ideas are unavailable (no Anthropic API key configured).",
        )

    try:
        data = json.loads(_strip_json(raw))
    except json.JSONDecodeError:
        logger.error("Activity suggester returned non-JSON")
        raise HTTPException(status_code=502, detail="The AI returned an unexpected response. Try again.")

    # Normalize / harden the shape before returning.
    suggestions = []
    for s in data.get("suggestions", []):
        ideas = []
        for idea in (s.get("ideas") or []):
            activity = str(idea.get("activity", "")).strip()
            if not activity:
                continue
            ideas.append({
                "activity": activity,
                "why": str(idea.get("why", "")).strip(),
                "how": str(idea.get("how", "")).strip(),
                "underused": bool(idea.get("underused", False)),
            })
        if ideas:
            suggestions.append({"objective": str(s.get("objective", "")).strip(), "ideas": ideas})

    if not suggestions:
        raise HTTPException(status_code=502, detail="The AI didn't return usable suggestions. Try again.")

    return {"suggestions": suggestions, "note": str(data.get("note", "")).strip()}
