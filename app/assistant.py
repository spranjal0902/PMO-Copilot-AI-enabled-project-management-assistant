
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .schema import _Tolerant
from .qa import ledger_context


def _default_llm(system_prompt: str, user_prompt: str) -> str:
    from .groq_client import groq_json
    return groq_json(system_prompt, user_prompt, temperature=0.1)


class EditOp(_Tolerant):
    op: str
    gid: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    priority: Optional[str] = None
    workstream: Optional[str] = None
    category: Optional[str] = None
    likelihood: Optional[str] = None
    impact: Optional[str] = None
    mitigation: Optional[str] = None
    compliance_flag: Optional[bool] = None
    decided_by: Optional[str] = None
    rationale: Optional[str] = None


class AssistantResponse(_Tolerant):
    is_edit: bool = False
    operations: list[EditOp] = []
    reply: str = ""


ASSIST_SYSTEM = """You are a PMO assistant with two jobs: answer questions about the project, \
and make edits when asked. Decide which the user wants.

If the user is ASKING something (status, what's blocking X, summarise, list…): set \
is_edit=false, operations=[], and put a concise, grounded answer in "reply" (cite ids/dates; \
if not in the data, say so).

If the user is INSTRUCTING a change (mark/set/change/add/update/close/assign/rename…): set \
is_edit=true, put a short confirmation in "reply", and list the operations. Available ops:
- {"op":"set_action_status","gid":"ACT-002","status":"done"}   (status: open|in_progress|blocked|done)
- {"op":"set_action_field","gid":"ACT-001","field":"owner|due_date|priority|description|workstream","value":"…"}
- {"op":"add_action","description":"…","owner":null,"priority":"medium","workstream":null,"status":"open"}
- {"op":"set_risk_field","gid":"RSK-001","field":"mitigation|status|likelihood|impact|category|compliance_flag","value":"…"}
- {"op":"add_risk","description":"…","category":"technical","likelihood":"medium","impact":"medium","compliance_flag":false}
- {"op":"add_decision","description":"…","decided_by":null,"rationale":null,"compliance_flag":false}

Use the exact ids shown in the project data. Be conservative: if it's not clearly an \
instruction to change something, treat it as a question. Return ONLY the JSON object with \
keys: is_edit, operations, reply."""


def respond(message: str, led: dict, llm=_default_llm) -> AssistantResponse:
    ctx = ledger_context(led) if (led and any(led.get(k) for k in
          ("tracked_actions", "tracked_risks", "decisions_log", "status_history"))) else "(empty project)"
    user = f"PROJECT DATA:\n{ctx}\n\nUSER MESSAGE: {message}"
    raw = llm(ASSIST_SYSTEM, user)
    return AssistantResponse.model_validate(json.loads(raw))


def _b(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def _find(items, gid):
    return next((it for it in items if it.get("gid") == gid), None)


def apply_edits(ledger, operations) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    log: list[str] = []
    for op in operations:
        kind = (op.op or "").strip()
        if kind == "set_action_status":
            a = _find(ledger.tracked_actions, op.gid)
            if not a:
                log.append(f"(no action {op.gid})"); continue
            ledger.update_action(op.gid, op.status or a["status"], today, note="set via chat")
            log.append(f"{op.gid} status → {op.status}")
        elif kind == "set_action_field":
            a = _find(ledger.tracked_actions, op.gid)
            if not a:
                log.append(f"(no action {op.gid})"); continue
            if op.field == "status":
                ledger.update_action(op.gid, op.value, today, note="set via chat")
            elif op.field in {"owner", "due_date", "priority", "description", "workstream"}:
                a[op.field] = op.value
                a["last_updated"] = today
                a["history"].append({"date": today, "status": a["status"],
                                     "note": f"{op.field} set to {op.value} via chat"})
            else:
                log.append(f"(unknown field {op.field})"); continue
            log.append(f"{op.gid} {op.field} → {op.value}")
        elif kind == "add_action":
            gid = ledger.add_action({"description": op.description, "owner": op.owner,
                                     "priority": op.priority or "medium",
                                     "workstream": op.workstream, "status": op.status or "open"}, today)
            log.append(f"added {gid}: {op.description}")
        elif kind == "set_risk_field":
            r = _find(ledger.tracked_risks, op.gid)
            if not r:
                log.append(f"(no risk {op.gid})"); continue
            if op.field == "compliance_flag":
                r["compliance_flag"] = _b(op.value)
            elif op.field in {"mitigation", "status", "likelihood", "impact", "category",
                              "description", "owner", "compliance_note"}:
                r[op.field] = op.value
            else:
                log.append(f"(unknown risk field {op.field})"); continue
            r["last_updated"] = today
            r["history"].append({"date": today, "status": r.get("status", "open"),
                                 "note": f"{op.field} set via chat"})
            log.append(f"{op.gid} {op.field} → {op.value}")
        elif kind == "add_risk":
            gid = ledger.add_risk({"description": op.description, "category": op.category or "technical",
                                   "likelihood": op.likelihood or "medium", "impact": op.impact or "medium",
                                   "mitigation": op.mitigation, "compliance_flag": bool(op.compliance_flag)}, today)
            log.append(f"added {gid}: {op.description}")
        elif kind == "add_decision":
            ledger.append_decisions([{"id": "D", "description": op.description, "decided_by": op.decided_by,
                                      "rationale": op.rationale, "reversible": True,
                                      "compliance_flag": bool(op.compliance_flag), "compliance_note": None}], today)
            log.append(f"logged decision: {op.description}")
        else:
            log.append(f"(unknown op {kind})")
    return log
