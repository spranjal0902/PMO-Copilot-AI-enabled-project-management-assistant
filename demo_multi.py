

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.store import ProjectLedger
from app.pipeline import ingest_meeting

LEDGER_PATH = "project_ledger.json"
MEETINGS = ["samples/helios_week1.txt", "samples/helios_week2.txt", "samples/helios_week3.txt"]


def show(ledger: ProjectLedger):
    print(f"\n================ PROJECT: {ledger.project_name} ================")
    print("\nTRACKED ACTIONS")
    for a in ledger.tracked_actions:
        print(f"  {a['gid']}  [{a['status']}]  {a['description']}")
        for h in a["history"]:
            print(f"        {h['date']}  ->  {h['status']} ({h['note']})")
    print("\nTRACKED RISKS")
    for r in ledger.tracked_risks:
        flag = "  ⚠ COMPLIANCE" if r.get("compliance_flag") else ""
        print(f"  {r['gid']}  [{r['status']}] {r['category']}{flag}: {r['description']}")
    print("\nDECISION LOG")
    for d in ledger.decisions_log:
        flag = "  ⚠" if d.get("compliance_flag") else ""
        print(f"  ({d.get('meeting_date')}) {d['description']}{flag}")
    print("\nLATEST STATUS PER WORKSTREAM")
    for ws, s in ledger.latest_status_by_workstream().items():
        print(f"  {ws}: {s['rag_status'].upper()}  (as of {s['meeting_date']})")


def main():
    if os.path.exists(LEDGER_PATH):
        os.remove(LEDGER_PATH)
    ledger = ProjectLedger()
    for path in MEETINGS:
        transcript = open(path, encoding="utf-8").read()
        print(f"\n>>> Ingesting {path} ...")
        ingest_meeting(ledger, transcript)     # real Groq extract + reconcile
        ledger.save(LEDGER_PATH)
    show(ledger)
    print(f"\nLedger saved to {LEDGER_PATH}")


if __name__ == "__main__":
    main()
