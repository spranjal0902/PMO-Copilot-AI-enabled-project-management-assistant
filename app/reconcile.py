"""
reconcile.py — Entity resolution across meetings.

THE PROBLEM: meeting 1 logs "re-run training on anonymised data" as A1. Three weeks
later meeting 3 says "training rerun is finished." Those are the SAME task — but the
ids don't line up (each meeting numbers from A1). Naive merging would create a duplicate
and the action would never look "done".

THE SOLUTION: before merging a new meeting, we show the model the project's currently
OPEN items plus the NEW meeting's items, and ask: for each new item, is it the same
underlying task as one of the open ones? This is classic record-linkage / entity
resolution — we just use an LLM to judge semantic sameness instead of brittle string
matching ("re-run training" vs "training rerun" would defeat a string match).

Same isolation principle as the extractor: the model call is injected, so this is
testable and provider-swappable.
"""

from __future__ import annotations
import os, json
from typing import Optional, Callable
from pydantic import BaseModel, Field, ConfigDict, AliasChoices


class Link(BaseModel):
    # Accept the model's natural field names too (index/status), not just our canonical
    # ones — JSON mode doesn't force exact names, so we stay tolerant and validate either.
    model_config = ConfigDict(populate_by_name=True)
    new_index: int = Field(validation_alias=AliasChoices("new_index", "index"))
    match_gid: Optional[str] = None
    new_status: Optional[str] = Field(default=None,
                                      validation_alias=AliasChoices("new_status", "status"))


class LinkResult(BaseModel):
    links: list[Link]


RECONCILE_SYSTEM = """You match items from a new project meeting against the project's \
currently open items, to avoid duplicates and to carry tasks across meetings.

For EACH new item (by its index), decide:
- If it refers to the SAME underlying task, risk, or workstream as an existing open item, \
put that item's gid in "match_gid" and the resulting status in "new_status" (e.g. 'done', \
'in_progress', 'blocked').
- If it is genuinely NEW, set "match_gid" to null.
Judge by meaning, not wording — e.g. "Backend API", "Backend scoring API" and "Backend \
integration" are the same workstream. Be conservative: only match when clearly the same thing.

Return JSON in EXACTLY this shape, using these exact field names:
{"links": [{"new_index": 0, "match_gid": "ACT-001", "new_status": "done"},
           {"new_index": 1, "match_gid": null, "new_status": "open"}]}
Return one link object per new item."""


def _build_prompt(open_items: list[dict], new_items: list[dict]) -> str:
    existing = "\n".join(f"- gid={i['gid']}: {i['description']} (status={i.get('status','open')})"
                         for i in open_items) or "(none open)"
    incoming = "\n".join(f"- index={idx}: {it['description']} (status={it.get('status','open')})"
                         for idx, it in enumerate(new_items)) or "(none)"
    return (f"CURRENTLY OPEN ITEMS:\n{existing}\n\n"
            f"NEW ITEMS FROM THIS MEETING:\n{incoming}\n\n"
            f"Return a link for every new item.")


def _default_llm(system_prompt: str, user_prompt: str) -> str:
    from .groq_client import groq_json
    return groq_json(system_prompt, user_prompt, temperature=0.0)


def reconcile(open_items: list[dict], new_items: list[dict],
              llm: Callable[[str, str], str] = _default_llm) -> LinkResult:
    if not new_items:
        return LinkResult(links=[])
    raw = llm(RECONCILE_SYSTEM, _build_prompt(open_items, new_items))
    return LinkResult.model_validate(json.loads(raw))
