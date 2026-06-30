"""
Runs the full pipeline with a FAKE model so we can validate schema + parsing
without any API key or network. Proves the contract holds end-to-end.
"""
from app.extractor import extract

# A stand-in for Gemini: returns a fixed JSON string shaped like real output.
FAKE_JSON = '''{
  "meta": {"project_name": "Project Helios", "meeting_date": "2025-06-18",
           "attendees": ["Marco", "Aisha", "Ben", "Sofia"]},
  "action_items": [
    {"id": "A1", "description": "Re-run model training on anonymised dataset",
     "owner": "Aisha", "due_date": "2025-06-30", "priority": "high",
     "workstream": "ML", "status": "open",
     "source_quote": "re-run training on the anonymised dataset by 30 June"}
  ],
  "risks": [
    {"id": "R1", "description": "Model trained on non-anonymised customer claims data",
     "category": "compliance", "likelihood": "high", "impact": "high",
     "mitigation": "Retrain on anonymised data with documented legal basis",
     "owner": "Sofia", "compliance_flag": true,
     "compliance_note": "GDPR: customer claims used for training without anonymisation"}
  ],
  "decisions": [
    {"id": "D1", "description": "No production release until compliance sign-off",
     "rationale": "Data-handling review must pass first", "decided_by": "Marco",
     "affected_workstreams": ["ML", "Backend"], "reversible": false,
     "compliance_flag": true, "compliance_note": "Release gated on data-handling review"},
    {"id": "D2", "description": "Use managed vector DB instead of self-hosting",
     "rationale": "Lower maintenance cost", "decided_by": "Marco",
     "affected_workstreams": ["Backend"], "reversible": true,
     "compliance_flag": false, "compliance_note": null}
  ],
  "status_updates": [
    {"workstream": "ML", "rag_status": "green",
     "summary": "Claims-scoring model at 89% accuracy", "blockers": []},
    {"workstream": "Backend", "rag_status": "amber",
     "summary": "Scoring API slipping, waiting on data contract",
     "blockers": ["Data contract from platform team"]}
  ]
}'''

def fake_llm(system_prompt, user_prompt):
    return FAKE_JSON

result = extract("(transcript ignored by fake model)", llm=fake_llm)

print("Project:", result.meta.project_name)
print("Actions:", len(result.action_items), "| Risks:", len(result.risks),
      "| Decisions:", len(result.decisions), "| Status updates:", len(result.status_updates))
flagged = [r.id for r in result.risks if r.compliance_flag] + \
          [d.id for d in result.decisions if d.compliance_flag]
print("Compliance-flagged items:", flagged)
print("Type returned:", type(result).__name__, "(validated OK)")
