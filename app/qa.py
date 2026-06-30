
from __future__ import annotations


def _default_llm(system_prompt: str, user_prompt: str) -> str:
    from .groq_client import groq_text
    return groq_text(system_prompt, user_prompt, temperature=0.2)


QA_SYSTEM = """You are a PMO (Project Management Office) assistant. Answer the user's \
question using ONLY the project data provided. Be concise and specific: cite item ids \
(ACT-…, RSK-…) and dates where relevant. If the answer is not in the project data, say \
you don't have that information rather than guessing. When asked to summarise for \
leadership, give 2-4 crisp sentences focused on status, risks, and what needs attention."""


def ledger_context(led: dict) -> str:
    """A compact, readable rendering of the whole project for the model to reason over."""
    lines = [f"PROJECT: {led.get('project_name', 'Untitled')}", ""]

    lines.append("ACTIONS:")
    for a in led.get("tracked_actions", []):
        hist = " | ".join(f"{h['date']}:{h['status']}" for h in a.get("history", []))
        lines.append(f"  {a['gid']} [{a.get('status')}] {a.get('description')} "
                     f"(owner={a.get('owner')}, due={a.get('due_date')}, "
                     f"workstream={a.get('workstream')}; history: {hist})")

    lines.append("\nRISKS:")
    for r in led.get("tracked_risks", []):
        flag = " COMPLIANCE" if r.get("compliance_flag") else ""
        lines.append(f"  {r['gid']} [{r.get('category')}{flag}] {r.get('description')} "
                     f"(likelihood={r.get('likelihood')}, impact={r.get('impact')}, "
                     f"mitigation={r.get('mitigation')})")

    lines.append("\nDECISIONS:")
    for d in led.get("decisions_log", []):
        flag = " COMPLIANCE" if d.get("compliance_flag") else ""
        lines.append(f"  ({d.get('meeting_date')}){flag} {d.get('description')} "
                     f"(by {d.get('decided_by')})")

    lines.append("\nLATEST STATUS PER WORKSTREAM:")
    latest: dict = {}
    for s in led.get("status_history", []):
        if s.get("workstream"):
            latest[s["workstream"]] = s
    for ws, s in latest.items():
        blk = ", ".join(s.get("blockers", []))
        lines.append(f"  {ws}: {s.get('rag_status')} — {s.get('summary')}"
                     + (f" (blockers: {blk})" if blk else ""))
    return "\n".join(lines)


def answer_question(question: str, led: dict, llm=_default_llm) -> str:
    has_data = led and (led.get("tracked_actions") or led.get("tracked_risks")
                        or led.get("decisions_log") or led.get("status_history"))
    if not has_data:
        return "There's no project yet — add a meeting first, then ask me about it."
    user = f"PROJECT DATA:\n{ledger_context(led)}\n\nQUESTION: {question}"
    return llm(QA_SYSTEM, user).strip()
