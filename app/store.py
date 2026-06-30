"""
store.py — The ProjectLedger: the project's memory across meetings.

A single MeetingExtraction is a snapshot of one meeting. The ledger is the running
state of the WHOLE project: actions that stay open across weeks, risks that evolve,
a growing decision log, and a history of status per workstream.

Each tracked item gets a STABLE global id (ACT-001, RSK-001) that persists across
meetings — unlike the per-meeting ids (A1, R1) which restart every meeting. That
stable id is what lets "opened in week 1, closed in week 3" be ONE item with a history,
instead of three disconnected rows.

Persistence here is a JSON file: dead simple, human-readable, perfect for a demo and
for local use. In production you'd swap this for a database (see future scope) — the
ProjectLedger class is the only thing that touches storage, so that swap is contained.
"""

from __future__ import annotations
import json, os
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


class ProjectLedger:
    def __init__(self, project_name: str = "Untitled Project"):
        self.project_name = project_name
        self.tracked_actions: list[dict] = []   # each has gid, description, owner, status, history[]
        self.tracked_risks: list[dict] = []      # each has gid, description, status, category, history[]
        self.decisions_log: list[dict] = []      # append-only: decisions are historical facts
        self.status_history: list[dict] = []      # per-meeting RAG snapshots per workstream
        self.canonical_workstreams: list[str] = []  # de-duplicated workstream names
        self._action_seq = 0
        self._risk_seq = 0

    # --- persistence ---------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "ProjectLedger":
        if not os.path.exists(path):
            return cls()
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        led = cls(d.get("project_name", "Untitled Project"))
        led.tracked_actions = d.get("tracked_actions", [])
        led.tracked_risks = d.get("tracked_risks", [])
        led.decisions_log = d.get("decisions_log", [])
        led.status_history = d.get("status_history", [])
        led.canonical_workstreams = d.get("canonical_workstreams", [])
        led._action_seq = d.get("_action_seq", len(led.tracked_actions))
        led._risk_seq = d.get("_risk_seq", len(led.tracked_risks))
        return led

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)

    # --- id minting ----------------------------------------------------------
    def _next_action_gid(self) -> str:
        self._action_seq += 1
        return f"ACT-{self._action_seq:03d}"

    def _next_risk_gid(self) -> str:
        self._risk_seq += 1
        return f"RSK-{self._risk_seq:03d}"

    # --- views for reconciliation -------------------------------------------
    def open_actions(self) -> list[dict]:
        return [a for a in self.tracked_actions if a["status"] != "done"]

    def open_risks(self) -> list[dict]:
        return [r for r in self.tracked_risks if r.get("status", "open") != "closed"]

    # --- mutations -----------------------------------------------------------
    def add_action(self, item: dict, meeting_date: Optional[str]) -> str:
        gid = self._next_action_gid()
        self.tracked_actions.append({
            "gid": gid,
            "description": item["description"],
            "owner": item.get("owner"),
            "due_date": item.get("due_date"),
            "priority": item.get("priority", "medium"),
            "workstream": item.get("workstream"),
            "status": item.get("status", "open"),
            "first_seen": meeting_date or _now(),
            "last_updated": meeting_date or _now(),
            "history": [{"date": meeting_date or _now(),
                         "status": item.get("status", "open"), "note": "created"}],
        })
        return gid

    def update_action(self, gid: str, new_status: str, meeting_date: Optional[str], note: str = "") -> None:
        for a in self.tracked_actions:
            if a["gid"] == gid:
                a["status"] = new_status
                a["last_updated"] = meeting_date or _now()
                a["history"].append({"date": meeting_date or _now(),
                                       "status": new_status, "note": note or "updated"})
                return

    def add_risk(self, item: dict, meeting_date: Optional[str]) -> str:
        gid = self._next_risk_gid()
        self.tracked_risks.append({
            "gid": gid,
            "description": item["description"],
            "category": item.get("category", "technical"),
            "likelihood": item.get("likelihood", "medium"),
            "impact": item.get("impact", "medium"),
            "mitigation": item.get("mitigation"),
            "owner": item.get("owner"),
            "compliance_flag": item.get("compliance_flag", False),
            "compliance_note": item.get("compliance_note"),
            "status": "open",
            "first_seen": meeting_date or _now(),
            "last_updated": meeting_date or _now(),
            "history": [{"date": meeting_date or _now(), "status": "open", "note": "created"}],
        })
        return gid

    def update_risk(self, gid: str, meeting_date: Optional[str], note: str = "", mitigation: Optional[str] = None) -> None:
        for r in self.tracked_risks:
            if r["gid"] == gid:
                r["last_updated"] = meeting_date or _now()
                if mitigation:
                    r["mitigation"] = mitigation
                r["history"].append({"date": meeting_date or _now(), "status": r["status"], "note": note or "updated"})
                return

    def append_decisions(self, decisions: list[dict], meeting_date: Optional[str]) -> None:
        for d in decisions:
            entry = dict(d)
            entry["meeting_date"] = meeting_date
            self.decisions_log.append(entry)

    def record_status(self, updates: list[dict], meeting_date: Optional[str]) -> None:
        for s in updates:
            entry = dict(s)
            entry["meeting_date"] = meeting_date
            self.status_history.append(entry)

    def latest_status_by_workstream(self) -> dict[str, dict]:
        latest: dict[str, dict] = {}
        for s in self.status_history:
            latest[s["workstream"]] = s   # later entries overwrite earlier -> most recent wins
        return latest
