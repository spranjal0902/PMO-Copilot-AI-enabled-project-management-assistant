
from __future__ import annotations
import os, json
from .schema import MeetingExtraction
from .prompts import SYSTEM_PROMPT, build_user_prompt


def _default_llm(system_prompt: str, user_prompt: str) -> str:
    from .groq_client import groq_json
    return groq_json(system_prompt, user_prompt, temperature=0.1)


_JUNK_DESCRIPTIONS = {
    "", "none", "none mentioned", "n/a", "na", "not mentioned",
    "no action", "no actions", "nothing", "no risk", "no decision",
}


def _is_junk(desc) -> bool:
    return (desc or "").strip().lower().rstrip(".") in _JUNK_DESCRIPTIONS


def extract(transcript: str, llm=_default_llm) -> MeetingExtraction:
    raw = llm(SYSTEM_PROMPT, build_user_prompt(transcript))
    data = json.loads(raw)
    # The real safety net: even if the model returns slightly-off JSON, Pydantic
    # validates types and enums and raises clearly instead of failing downstream.
    me = MeetingExtraction.model_validate(data)
    # Drop placeholder rows the model sometimes invents (e.g. "None mentioned").
    me.action_items = [a for a in me.action_items if not _is_junk(a.description)]
    me.risks = [r for r in me.risks if not _is_junk(r.description)]
    me.decisions = [d for d in me.decisions if not _is_junk(d.description)]
    return me
