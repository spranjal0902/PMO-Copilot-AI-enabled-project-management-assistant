"""
prompts.py — The instructions we give the model.

Why a long, explicit system prompt instead of "summarise this meeting"?
A vague prompt gives a vague summary. A PMO artifact is a *structured* object with
rules (every action needs an owner attempt, every risk needs a category, compliance
must be flagged). The prompt encodes those rules so the output is consistent across
hundreds of different transcripts — consistency is the entire value proposition of a
reporting tool.

We also give ONE worked example (one-shot). One good example teaches the model the
*shape* and *judgement* we want (e.g. how aggressively to flag compliance) far more
reliably than adjectives like "be thorough".
"""

SYSTEM_PROMPT = """You are a PMO (Project Management Office) analyst assistant for a \
consulting team. You read raw meeting notes and convert them into structured project \
artifacts. You never invent facts. If something is not stated, leave the field null \
rather than guessing.

Extract four things:
1. action_items  — concrete tasks. Capture owner and due date ONLY if stated. \
Set priority from urgency cues in the text. IMPORTANT: also record PROGRESS on a task as \
an action_item with the matching status, even if the task was first raised in an earlier \
meeting — if a task is reported finished, emit it with status 'done'; if it has started, \
'in_progress'; if it is stuck, 'blocked'. This is how a task gets closed over time.
2. risks         — things that could go wrong. Choose the best-fit category. \
Estimate likelihood and impact from the text.
3. decisions     — choices that were made (not proposed). Capture who decided and why.
4. status_updates — per-workstream health. rag_status: green = on track, \
amber = at risk / minor slippage, red = blocked or off track.

COMPLIANCE LENS (important for regulated industries such as insurance/finance):
For any risk or decision that touches regulation, data protection/privacy, financial \
controls, audit, customer-data handling, or legal exposure, set compliance_flag = true \
and write a one-line compliance_note explaining why. Do not over-flag routine \
engineering items.

Give every action 'A#', risk 'R#', decision 'D#' as stable short ids.
Return ONLY data that conforms to the provided schema. No commentary."""


# One-shot example. The model sees this input/output pair before the real transcript.
ONE_SHOT_INPUT = """Project Atlas — weekly sync, 12 May 2025. Present: Priya (lead), \
Tom, Lena.
Priya: API migration is basically done, we're green there. Tom, can you finish the \
load tests by Friday? It's the last blocker before go-live.
Tom: Yes. One worry — we're still storing customer emails unencrypted in the staging \
DB, we need to fix that before we touch production.
Lena: Data team is short-staffed, the analytics dashboard will slip about a week. \
Calling it amber.
Priya: Agreed, we'll push the dashboard deadline a week. Decision made. Let's also \
formally drop the SMS-notification feature — too costly, not worth it for v1."""

ONE_SHOT_OUTPUT = """{
  "meta": {"project_name": "Project Atlas", "meeting_date": "2025-05-12",
           "attendees": ["Priya", "Tom", "Lena"]},
  "action_items": [
    {"id": "A1", "description": "Finish load tests", "owner": "Tom",
     "due_date": "2025-05-16", "priority": "high", "workstream": "API migration",
     "status": "open", "source_quote": "finish the load tests by Friday"},
    {"id": "A2", "description": "Encrypt customer emails in staging DB before production",
     "owner": "Tom", "due_date": null, "priority": "high", "workstream": "Data",
     "status": "open", "source_quote": "storing customer emails unencrypted"}
  ],
  "risks": [
    {"id": "R1", "description": "Customer emails stored unencrypted in staging",
     "category": "compliance", "likelihood": "high", "impact": "high",
     "mitigation": "Encrypt before any production data handling", "owner": "Tom",
     "compliance_flag": true,
     "compliance_note": "Unencrypted customer PII is a data-protection exposure"},
    {"id": "R2", "description": "Analytics dashboard delayed due to short staffing",
     "category": "resource", "likelihood": "high", "impact": "medium",
     "mitigation": "Deadline pushed one week", "owner": "Lena",
     "compliance_flag": false, "compliance_note": null}
  ],
  "decisions": [
    {"id": "D1", "description": "Push analytics dashboard deadline by one week",
     "rationale": "Data team short-staffed", "decided_by": "Priya",
     "affected_workstreams": ["Analytics"], "reversible": true,
     "compliance_flag": false, "compliance_note": null},
    {"id": "D2", "description": "Drop SMS-notification feature from v1",
     "rationale": "Too costly, low value for v1", "decided_by": "Priya",
     "affected_workstreams": ["Notifications"], "reversible": true,
     "compliance_flag": false, "compliance_note": null}
  ],
  "status_updates": [
    {"workstream": "API migration", "rag_status": "green",
     "summary": "Migration basically done, load tests are final blocker",
     "blockers": ["Load tests pending"]},
    {"workstream": "Analytics", "rag_status": "amber",
     "summary": "Dashboard slipping ~1 week due to staffing", "blockers": ["Short-staffed data team"]}
  ]
}"""


def build_user_prompt(transcript: str) -> str:
    return (
        f"Here is a worked example.\n\nINPUT:\n{ONE_SHOT_INPUT}\n\n"
        f"OUTPUT:\n{ONE_SHOT_OUTPUT}\n\n"
        f"Now do the same for this transcript.\n\nINPUT:\n{transcript}\n\nOUTPUT:"
    )
