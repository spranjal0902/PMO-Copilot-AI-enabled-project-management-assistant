

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator

class _Tolerant(BaseModel):

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data):
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None}
        return data

class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ItemStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class RAG(str, Enum):
    red = "red"
    amber = "amber"
    green = "green"


class Level(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RiskCategory(str, Enum):
    technical = "technical"
    schedule = "schedule"
    resource = "resource"
    financial = "financial"
    compliance = "compliance"   
    external = "external"


class ActionItem(_Tolerant):
    id: str = Field(description="Stable short id, e.g. 'A1'")
    description: str
    owner: Optional[str] = Field(None, description="Person/team accountable, if stated")
    due_date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD if a date is given")
    priority: Priority = Priority.medium
    workstream: Optional[str] = None
    status: ItemStatus = ItemStatus.open
    source_quote: Optional[str] = Field(
        None, description="The phrase in the transcript this was derived from (traceability)"
    )


class Risk(_Tolerant):
    id: str = Field(description="Stable short id, e.g. 'R1'")
    description: str
    category: RiskCategory = RiskCategory.technical
    likelihood: Level = Level.medium
    impact: Level = Level.medium
    mitigation: Optional[str] = None
    owner: Optional[str] = None
    compliance_flag: bool = False
    compliance_note: Optional[str] = None


class Decision(_Tolerant):
    id: str = Field(description="Stable short id, e.g. 'D1'")
    description: str
    rationale: Optional[str] = None
    decided_by: Optional[str] = None
    affected_workstreams: list[str] = Field(default_factory=list)
    reversible: bool = True
    compliance_flag: bool = False
    compliance_note: Optional[str] = None


class StatusUpdate(_Tolerant):
    workstream: str
    rag_status: RAG = RAG.amber
    summary: str
    blockers: list[str] = Field(default_factory=list)


class MeetingMeta(_Tolerant):
    project_name: Optional[str] = None
    meeting_date: Optional[str] = None
    attendees: list[str] = Field(default_factory=list)


class MeetingExtraction(_Tolerant):
    meta: MeetingMeta = Field(default_factory=MeetingMeta)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    status_updates: list[StatusUpdate] = Field(default_factory=list)
