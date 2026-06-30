"""Unit-tests workstream consolidation: differently-named workstreams collapse to one."""
import json, re
from types import SimpleNamespace
from app.store import ProjectLedger
from app.pipeline import _canonicalize_workstreams

def ws(n): return SimpleNamespace(workstream=n)

def stub_allnew(s, u):
    idx = re.findall(r"index=(\d+):", u)
    return json.dumps({"links": [{"new_index": int(i), "match_gid": None, "new_status": "open"} for i in idx]})

def stub_match_backend(s, u):
    return json.dumps({"links": [{"new_index": 0, "match_gid": "Backend API", "new_status": "open"}]})

ledger = ProjectLedger()
# Meeting 1 introduces "Backend API"
m1 = SimpleNamespace(status_updates=[ws("Backend API")], action_items=[])
_canonicalize_workstreams(ledger, m1, stub_allnew)
print("after meeting 1, canonical:", ledger.canonical_workstreams)

# Meeting 2 says "Backend scoring API" -> should map onto the existing canonical, not add a new one
m2 = SimpleNamespace(status_updates=[ws("Backend scoring API")], action_items=[])
mapping = _canonicalize_workstreams(ledger, m2, stub_match_backend)
print("meeting 2 mapping:", mapping)
print("after meeting 2, canonical:", ledger.canonical_workstreams)

assert ledger.canonical_workstreams == ["Backend API"], "should NOT have added a duplicate workstream"
assert mapping["Backend scoring API"] == "Backend API", "variant should map to canonical"
print("PASS: 'Backend scoring API' consolidated into 'Backend API' (no duplicate)")
