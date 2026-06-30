"""
Verifies the CROSS-MEETING merge logic. The two LLM steps are stubbed (sandbox has no
Gemini access), but the stubs feed realistic structured output so the deterministic
ledger-merge logic gets a genuine workout. The reconcile stub does real keyword-overlap
matching parsed from the prompt -- it is NOT hardcoded to the answer.
"""
import json, re
from app.store import ProjectLedger
from app.pipeline import ingest_meeting

# --- three meetings of ONE project, as the extractor would return them -------
M1 = {"meta":{"project_name":"Project Helios","meeting_date":"2025-06-04","attendees":["Marco","Aisha"]},
 "action_items":[{"id":"A1","description":"Re-run model training on anonymised dataset","owner":"Aisha","due_date":"2025-06-30","priority":"high","workstream":"ML","status":"open","source_quote":"re-run training"}],
 "risks":[{"id":"R1","description":"Model trained on non-anonymised customer claims data","category":"compliance","likelihood":"high","impact":"high","mitigation":None,"owner":"Sofia","compliance_flag":True,"compliance_note":"GDPR exposure"}],
 "decisions":[],"status_updates":[{"workstream":"ML","rag_status":"amber","summary":"Retrain needed","blockers":["Anonymisation pending"]}]}

M2 = {"meta":{"project_name":"Project Helios","meeting_date":"2025-06-11","attendees":["Marco","Aisha"]},
 "action_items":[{"id":"A1","description":"Anonymised training rerun still in progress, blocked on data access","owner":"Aisha","due_date":"2025-06-30","priority":"high","workstream":"ML","status":"blocked","source_quote":"still working on the rerun"}],
 "risks":[{"id":"R1","description":"Customer claims data not yet anonymised for training","category":"compliance","likelihood":"high","impact":"high","mitigation":"Anonymisation in progress","owner":"Sofia","compliance_flag":True,"compliance_note":"GDPR exposure"}],
 "decisions":[],"status_updates":[{"workstream":"ML","rag_status":"amber","summary":"Rerun blocked on data access","blockers":["Data access"]}]}

M3 = {"meta":{"project_name":"Project Helios","meeting_date":"2025-06-18","attendees":["Marco","Aisha"]},
 "action_items":[{"id":"A1","description":"Training rerun on anonymised data completed","owner":"Aisha","due_date":"2025-06-30","priority":"high","workstream":"ML","status":"done","source_quote":"rerun is finished"}],
 "risks":[{"id":"R1","description":"Customer claims data anonymisation completed for training","category":"compliance","likelihood":"low","impact":"high","mitigation":"Done, documented basis recorded","owner":"Sofia","compliance_flag":True,"compliance_note":"Now mitigated"}],
 "decisions":[{"id":"D1","description":"Approve model for production after sign-off","rationale":"Compliance cleared","decided_by":"Marco","affected_workstreams":["ML"],"reversible":False,"compliance_flag":True,"compliance_note":"Release gated on review"}],
 "status_updates":[{"workstream":"ML","rag_status":"green","summary":"Retrained, compliant","blockers":[]}]}

FIXTURES = {"M1": M1, "M2": M2, "M3": M3}

def make_extract_stub(marker):
    return lambda system, user: json.dumps(FIXTURES[marker])

def reconcile_stub(system, user):
    """Real keyword-overlap matching parsed from the prompt -- not hardcoded."""
    open_items = re.findall(r"gid=(\S+): (.+?) \(status=", user)
    new_items  = re.findall(r"index=(\d+): (.+?) \(status=(\w+)\)", user)
    def toks(s): return set(re.findall(r"[a-z]+", s.lower())) - {"the","a","on","of","for","and","to","in","not"}
    links = []
    for idx, desc, status in new_items:
        best, best_score = None, 0.0
        for gid, odesc in open_items:
            inter = toks(desc) & toks(odesc); union = toks(desc) | toks(odesc)
            score = len(inter)/len(union) if union else 0
            if score > best_score: best, best_score = gid, score
        if best and best_score >= 0.15:
            links.append({"new_index": int(idx), "match_gid": best, "new_status": status})
        else:
            links.append({"new_index": int(idx), "match_gid": None, "new_status": status})
    return json.dumps({"links": links})

ledger = ProjectLedger()
for marker in ["M1", "M2", "M3"]:
    ingest_meeting(ledger, f"transcript {marker}",
                   extract_llm=make_extract_stub(marker), reconcile_llm=reconcile_stub)

print("=== TRACKED ACTIONS (should be ONE, not three) ===")
for a in ledger.tracked_actions:
    print(f"{a['gid']}: {a['description'][:45]}... status={a['status']}")
    for h in a["history"]:
        print(f"    {h['date']}  ->  {h['status']:12s} ({h['note']})")

print("\n=== TRACKED RISKS (should be ONE, carried across) ===")
for r in ledger.tracked_risks:
    print(f"{r['gid']}: status={r['status']} compliance_flag={r['compliance_flag']} updates={len(r['history'])}")

print("\n=== DECISIONS LOG ===", len(ledger.decisions_log), "decision(s)")
print("=== LATEST STATUS PER WORKSTREAM ===")
for ws, s in ledger.latest_status_by_workstream().items():
    print(f"   {ws}: {s['rag_status']} (as of {s['meeting_date']})")
