
from __future__ import annotations
from typing import Optional
from .extractor import extract, _default_llm as _extract_llm
from .reconcile import reconcile, _default_llm as _reconcile_llm
from .store import ProjectLedger


def _canonicalize_workstreams(ledger: ProjectLedger, me, reconcile_llm) -> dict:
    names: list[str] = []
    for s in me.status_updates:
        if s.workstream and s.workstream not in names:
            names.append(s.workstream)
    for a in me.action_items:
        if a.workstream and a.workstream not in names:
            names.append(a.workstream)
    if not names:
        return {}

    existing = [{"gid": w, "description": w} for w in ledger.canonical_workstreams]
    new_items = [{"description": n} for n in names]
    links = reconcile(existing, new_items, llm=reconcile_llm).links
    matched = {l.new_index: l for l in links}

    mapping: dict = {}
    for idx, name in enumerate(names):
        link = matched.get(idx)
        if link and link.match_gid:
            mapping[name] = link.match_gid          # variant -> canonical
        else:
            ledger.canonical_workstreams.append(name)
            mapping[name] = name                      # new canonical
    return mapping

def ingest_meeting(ledger: ProjectLedger, transcript: str,
                   extract_llm=_extract_llm, reconcile_llm=_reconcile_llm) -> ProjectLedger:
    me = extract(transcript, llm=extract_llm)
    return commit_meeting(ledger, me, reconcile_llm=reconcile_llm)


def commit_meeting(ledger: ProjectLedger, me, reconcile_llm=_reconcile_llm) -> ProjectLedger:
    meeting_date = me.meta.meeting_date
    if me.meta.project_name and ledger.project_name == "Untitled Project":
        ledger.project_name = me.meta.project_name

    ws_map = _canonicalize_workstreams(ledger, me, reconcile_llm)
    for s in me.status_updates:
        if s.workstream:
            s.workstream = ws_map.get(s.workstream, s.workstream)
    for a in me.action_items:
        if a.workstream:
            a.workstream = ws_map.get(a.workstream, a.workstream)

    new_actions = [a.model_dump(mode="json") for a in me.action_items]
    links = reconcile(ledger.open_actions(), new_actions, llm=reconcile_llm).links
    matched = {l.new_index: l for l in links}
    for idx, item in enumerate(new_actions):
        link = matched.get(idx)
        if link and link.match_gid:
            ledger.update_action(link.match_gid, link.new_status or item["status"],
                                 meeting_date, note=f"updated from meeting {meeting_date}")
        else:
            ledger.add_action(item, meeting_date)

    new_risks = [r.model_dump(mode="json") for r in me.risks]
    rlinks = reconcile(ledger.open_risks(), new_risks, llm=reconcile_llm).links
    rmatched = {l.new_index: l for l in rlinks}
    for idx, item in enumerate(new_risks):
        link = rmatched.get(idx)
        if link and link.match_gid:
            ledger.update_risk(link.match_gid, meeting_date,
                               note=f"revisited in meeting {meeting_date}",
                               mitigation=item.get("mitigation"))
        else:
            ledger.add_risk(item, meeting_date)

    ledger.append_decisions([d.model_dump(mode="json") for d in me.decisions], meeting_date)

    ledger.record_status([s.model_dump(mode="json") for s in me.status_updates], meeting_date)

    return ledger
