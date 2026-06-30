
from __future__ import annotations
import json, os, sys, html
from datetime import datetime

LEDGER_PATH = "project_ledger.json"
OUT_PATH = "dashboard.html"

RAG = {"green": "#15803D", "amber": "#B45309", "red": "#B91C1C"}
RAG_TINT = {"green": "#ECFDF3", "amber": "#FEF6EC", "red": "#FEF1F1"}
STATUS_COLOR = {"open": "#64748B", "in_progress": "#1D4ED8", "blocked": "#B91C1C", "done": "#15803D"}
COMPLIANCE = "#6D28D9"    

def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def latest_status_by_workstream(status_history: list[dict]) -> dict:
    latest: dict[str, dict] = {}
    for s in status_history:
        ws = s.get("workstream")
        if ws:
            latest[ws] = s
            return latest


def kpi_strip(led: dict) -> str:
    actions = led.get("tracked_actions", [])
    risks = led.get("tracked_risks", [])
    decisions = led.get("decisions_log", [])
    done = sum(1 for a in actions if a.get("status") == "done")
    open_n = sum(1 for a in actions if a.get("status") != "done")
    compliance = (sum(1 for r in risks if r.get("compliance_flag")) +
                  sum(1 for d in decisions if d.get("compliance_flag")))
    ws = len(latest_status_by_workstream(led.get("status_history", [])))
    cells = [
        ("Workstreams", ws, None),
        ("Open actions", open_n, None),
        ("Completed", done, "#15803D"),
        ("Open risks", len(risks), None),
        ("Compliance flags", compliance, COMPLIANCE if compliance else None),
        ("Decisions logged", len(decisions), None),
    ]
    out = []
    for label, val, color in cells:
        style = f' style="color:{color}"' if color else ""
        out.append(
            f'<div class="kpi"><div class="kpi-num"{style}>{val}</div>'
            f'<div class="kpi-label">{esc(label)}</div></div>')
    return f'<div class="kpis">{"".join(out)}</div>'


def rag_board(led: dict) -> str:
    latest = latest_status_by_workstream(led.get("status_history", []))
    if not latest:
        return ""
    tiles = []
    for ws, s in latest.items():
        rag = s.get("rag_status", "amber")
        color, tint = RAG.get(rag, "#64748B"), RAG_TINT.get(rag, "#F1F5F9")
        blockers = s.get("blockers") or []
        block_html = ""
        if blockers:
            items = "".join(f"<li>{esc(b)}</li>" for b in blockers)
            block_html = f'<ul class="blockers">{items}</ul>'
        tiles.append(
            f'<div class="tile" style="border-left-color:{color};background:{tint}">'
            f'<div class="tile-top"><span class="tile-ws">{esc(ws)}</span>'
            f'<span class="rag-chip" style="background:{color}">{esc(rag).upper()}</span></div>'
            f'<div class="tile-summary">{esc(s.get("summary",""))}</div>'
            f'{block_html}'
            f'<div class="tile-date">as of {esc(s.get("meeting_date","—"))}</div></div>')
    return ('<section><h2>Status board</h2>'
            f'<div class="tiles">{"".join(tiles)}</div></section>')


def lifecycle(history: list[dict]) -> str:
    """The signature element: an action's status journey across meetings."""
    if not history:
        return ""
    nodes = []
    for h in history:
        st = h.get("status", "open")
        c = STATUS_COLOR.get(st, "#64748B")
        nodes.append(
            f'<div class="node"><span class="dot" style="background:{c}"></span>'
            f'<span class="node-status" style="color:{c}">{esc(st)}</span>'
            f'<span class="node-date">{esc(h.get("date","—"))}</span></div>')
    return f'<div class="lifecycle">{"".join(nodes)}</div>'


def action_tracker(led: dict) -> str:
    actions = led.get("tracked_actions", [])
    if not actions:
        return ""
    rows = []
    for a in actions:
        st = a.get("status", "open")
        c = STATUS_COLOR.get(st, "#64748B")
        meta = []
        if a.get("owner"): meta.append(f'owner: {esc(a["owner"])}')
        if a.get("workstream"): meta.append(esc(a["workstream"]))
        if a.get("due_date"): meta.append(f'due {esc(a["due_date"])}')
        if a.get("priority"): meta.append(f'{esc(a["priority"])} priority')
        meta_html = '  ·  '.join(meta)
        rows.append(
            f'<div class="action">'
            f'<div class="action-head">'
            f'<span class="gid">{esc(a.get("gid",""))}</span>'
            f'<span class="status-badge" style="background:{c}1A;color:{c};border-color:{c}55">{esc(st)}</span>'
            f'<span class="action-desc">{esc(a.get("description",""))}</span></div>'
            f'<div class="action-meta">{meta_html}</div>'
            f'{lifecycle(a.get("history", []))}</div>')
    return '<section><h2>Action tracker</h2>' + "".join(rows) + '</section>'


def risk_register(led: dict) -> str:
    risks = led.get("tracked_risks", [])
    if not risks:
        return ""
    rows = []
    for r in risks:
        comp = r.get("compliance_flag")
        accent = COMPLIANCE if comp else "#CBD5E1"
        chip = (f'<span class="comp-chip">⚠ COMPLIANCE</span>' if comp else "")
        li = f'{esc(r.get("likelihood","—"))} likelihood · {esc(r.get("impact","—"))} impact'
        mitig = (f'<div class="risk-mitig"><span class="lbl">Mitigation</span> {esc(r["mitigation"])}</div>'
                 if r.get("mitigation") else "")
        note = (f'<div class="risk-note">{esc(r.get("compliance_note",""))}</div>'
                if comp and r.get("compliance_note") else "")
        rows.append(
            f'<div class="risk" style="border-left-color:{accent}">'
            f'<div class="risk-head"><span class="gid">{esc(r.get("gid",""))}</span>'
            f'<span class="cat">{esc(r.get("category","—"))}</span>{chip}</div>'
            f'<div class="risk-desc">{esc(r.get("description",""))}</div>'
            f'<div class="risk-li">{li}</div>{mitig}{note}</div>')
    return '<section><h2>Risk register</h2>' + "".join(rows) + '</section>'


def decision_log(led: dict) -> str:
    decisions = led.get("decisions_log", [])
    if not decisions:
        return ""
    rows = []
    for d in decisions:
        comp = d.get("compliance_flag")
        chip = '<span class="comp-chip">⚠ COMPLIANCE</span>' if comp else ""
        sub = []
        if d.get("decided_by"): sub.append(f'decided by {esc(d["decided_by"])}')
        if d.get("rationale"): sub.append(esc(d["rationale"]))
        rows.append(
            f'<div class="decision">'
            f'<span class="dec-date">{esc(d.get("meeting_date","—"))}</span>'
            f'<div class="dec-body"><div class="dec-desc">{esc(d.get("description",""))} {chip}</div>'
            f'<div class="dec-sub">{"  ·  ".join(sub)}</div></div></div>')
    return '<section><h2>Decision log</h2>' + "".join(rows) + '</section>'


CSS = """
:root{--ink:#15213B;--muted:#5B6472;--line:#E5E8EE;--bg:#F7F8FA;--card:#fff;--comp:#6D28D9}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
.wrap{max-width:1040px;margin:0 auto;padding:40px 28px 72px}
header{border-bottom:2px solid var(--ink);padding-bottom:22px;margin-bottom:30px}
.eyebrow{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--muted)}
h1{font-size:34px;font-weight:680;margin:8px 0 6px;letter-spacing:-.01em}
.sub{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:26px 0 6px}
.kpi{background:var(--card);padding:16px 14px}
.kpi-num{font-family:ui-monospace,Menlo,monospace;font-size:26px;font-weight:600;letter-spacing:-.02em}
.kpi-label{font-size:11px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.04em}
section{margin-top:38px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);
  font-weight:680;margin:0 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:12px}
.tile{border:1px solid var(--line);border-left-width:4px;border-radius:9px;padding:14px 15px}
.tile-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.tile-ws{font-weight:640;font-size:14px}
.rag-chip{color:#fff;font-family:ui-monospace,Menlo,monospace;font-size:10px;font-weight:600;
  letter-spacing:.08em;padding:2px 7px;border-radius:5px}
.tile-summary{font-size:13px;color:#374151;margin:8px 0}
.blockers{margin:6px 0 0;padding-left:16px;font-size:12px;color:var(--muted)}
.tile-date{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted);margin-top:8px}
.action{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:15px 17px;margin-bottom:10px}
.action-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.gid{font-family:ui-monospace,Menlo,monospace;font-size:12px;font-weight:600;color:var(--ink);
  background:#EEF1F6;padding:2px 7px;border-radius:5px}
.status-badge{font-family:ui-monospace,Menlo,monospace;font-size:11px;padding:2px 8px;
  border-radius:5px;border:1px solid;font-weight:600}
.action-desc{font-size:15px;font-weight:540}
.action-meta{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--muted);margin:8px 0 0 2px}
.lifecycle{display:flex;flex-wrap:wrap;gap:0;margin-top:13px;padding-top:12px;border-top:1px dashed var(--line)}
.node{display:flex;flex-direction:column;align-items:flex-start;position:relative;padding-right:34px;min-width:96px}
.node:not(:last-child)::after{content:"";position:absolute;top:5px;left:11px;right:8px;height:2px;background:var(--line)}
.dot{width:11px;height:11px;border-radius:50%;display:inline-block;z-index:1}
.node-status{font-family:ui-monospace,Menlo,monospace;font-size:11px;font-weight:600;margin-top:6px}
.node-date{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:var(--muted);margin-top:1px}
.risk{background:var(--card);border:1px solid var(--line);border-left-width:4px;border-radius:9px;
  padding:14px 16px;margin-bottom:10px}
.risk-head{display:flex;align-items:center;gap:10px}
.cat{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.comp-chip{font-family:ui-monospace,Menlo,monospace;font-size:10px;font-weight:700;color:#fff;
  background:var(--comp);padding:2px 7px;border-radius:5px;letter-spacing:.04em}
.risk-desc{font-size:14.5px;font-weight:540;margin:8px 0 5px}
.risk-li{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--muted)}
.risk-mitig{font-size:13px;margin-top:7px;color:#374151}
.risk-mitig .lbl,.risk-note{font-family:ui-monospace,Menlo,monospace}
.risk-mitig .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-right:6px}
.risk-note{font-size:12px;color:var(--comp);margin-top:6px;background:#F5F3FF;padding:6px 9px;border-radius:6px}
.decision{display:flex;gap:14px;padding:12px 2px;border-bottom:1px solid var(--line)}
.dec-date{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--muted);white-space:nowrap;padding-top:2px}
.dec-desc{font-size:14.5px;font-weight:540}
.dec-sub{font-size:12.5px;color:var(--muted);margin-top:3px}
footer{margin-top:48px;padding-top:18px;border-top:1px solid var(--line);
  font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted)}
@media(max-width:760px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media print{body{background:#fff}.action,.risk,.tile{break-inside:avoid}}
"""


def build(led: dict) -> str:
    project = led.get("project_name", "Untitled Project")
    now = datetime.now().strftime("%d %b %Y, %H:%M")
    body = (kpi_strip(led) + rag_board(led) + action_tracker(led)
            + risk_register(led) + decision_log(led))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(project)} — PMO status</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <div class="eyebrow">PMO Copilot · Project status report</div>
  <h1>{esc(project)}</h1>
  <div class="sub">Generated {esc(now)} · synthesised from meeting transcripts</div>
</header>
{body}
<footer>Auto-generated from the project ledger · compliance flags indicate items touching
regulation, data protection, or audit and require human review.</footer>
</div></body></html>"""


def main():
    if not os.path.exists(LEDGER_PATH):
        print(f"No {LEDGER_PATH} found. Run `python demo_multi.py` first to create it.")
        sys.exit(1)
    with open(LEDGER_PATH, encoding="utf-8") as f:
        led = json.load(f)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(build(led))
    print(f"Wrote {OUT_PATH} — open it in your browser.")


if __name__ == "__main__":
    main()
