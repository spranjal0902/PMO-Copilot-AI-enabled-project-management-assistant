
from __future__ import annotations
import os, sys, json, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import gradio as gr

from app.extractor import extract
from app.pipeline import commit_meeting
from app.store import ProjectLedger
from app.schema import MeetingExtraction
from app.assistant import respond, apply_edits
from app.vision import transcribe_image
from app.export_office import export_excel, export_word
from build_dashboard import build as build_dashboard_html

LEDGER_PATH = "project_ledger.json"

ACTION_COLS = ["id", "description", "owner", "due_date", "priority", "workstream", "status"]
RISK_COLS = ["id", "description", "category", "likelihood", "impact", "mitigation",
             "owner", "compliance_flag", "compliance_note"]
DECISION_COLS = ["id", "description", "decided_by", "rationale", "reversible",
                 "compliance_flag", "compliance_note"]
STATUS_COLS = ["workstream", "rag_status", "summary", "blockers"]

SAMPLE = """Project Helios — weekly sync, 4 June 2025. Present: Marco (PM), Aisha (ML), Ben (backend), Sofia (compliance).
Aisha: The claims-scoring model hits 89% accuracy. But heads up — we trained on real customer claims data that wasn't anonymised first.
Sofia: That's a GDPR problem. We can't use raw customer claims for training without anonymisation and a documented legal basis. Must fix before anything goes live.
Marco: Understood. Aisha, please re-run training on the anonymised dataset by 30 June — high priority.
Ben: Backend scoring API isn't ready, I'd call it amber. Blocker is the data contract from the platform team.
Marco: Decision: no production release until Sofia signs off on the data-handling review. Firm."""


def _b(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def _me_to_frames(me: MeetingExtraction):
    a = pd.DataFrame([[x.id, x.description, x.owner, x.due_date, x.priority.value,
                       x.workstream, x.status.value] for x in me.action_items], columns=ACTION_COLS)
    r = pd.DataFrame([[x.id, x.description, x.category.value, x.likelihood.value, x.impact.value,
                       x.mitigation, x.owner, x.compliance_flag, x.compliance_note]
                      for x in me.risks], columns=RISK_COLS)
    d = pd.DataFrame([[x.id, x.description, x.decided_by, x.rationale, x.reversible,
                       x.compliance_flag, x.compliance_note] for x in me.decisions], columns=DECISION_COLS)
    s = pd.DataFrame([[x.workstream, x.rag_status.value, x.summary, "; ".join(x.blockers)]
                      for x in me.status_updates], columns=STATUS_COLS)
    return a, r, d, s


def _frames_to_me(project_name, meeting_date, a, r, d, s) -> MeetingExtraction:
    def rows(df):
        return [] if df is None else df.fillna("").values.tolist()
    actions = [{"id": x[0] or f"A{i+1}", "description": x[1], "owner": x[2] or None,
                "due_date": x[3] or None, "priority": x[4] or None, "workstream": x[5] or None,
                "status": x[6] or None} for i, x in enumerate(rows(a)) if str(x[1]).strip()]
    risks = [{"id": x[0] or f"R{i+1}", "description": x[1], "category": x[2] or None,
              "likelihood": x[3] or None, "impact": x[4] or None, "mitigation": x[5] or None,
              "owner": x[6] or None, "compliance_flag": _b(x[7]), "compliance_note": x[8] or None}
             for i, x in enumerate(rows(r)) if str(x[1]).strip()]
    decisions = [{"id": x[0] or f"D{i+1}", "description": x[1], "decided_by": x[2] or None,
                  "rationale": x[3] or None, "reversible": _b(x[4]),
                  "compliance_flag": _b(x[5]), "compliance_note": x[6] or None}
                 for i, x in enumerate(rows(d)) if str(x[1]).strip()]
    status = [{"workstream": x[0], "rag_status": x[1] or None, "summary": x[2],
               "blockers": [b.strip() for b in str(x[3]).replace(",", ";").split(";") if b.strip()]}
              for x in rows(s) if str(x[0]).strip()]
    return MeetingExtraction.model_validate({
        "meta": {"project_name": project_name or None, "meeting_date": meeting_date or None},
        "action_items": actions, "risks": risks, "decisions": decisions, "status_updates": status})


def _dashboard_iframe() -> str:
    if not os.path.exists(LEDGER_PATH):
        return ("<div style='padding:40px;text-align:center;color:#6B7280;font-family:sans-serif'>"
                "No project yet — drop in some notes above, review the draft, and approve.</div>")
    with open(LEDGER_PATH, encoding="utf-8") as f:
        led = json.load(f)
    doc = build_dashboard_html(led)
    safe = html.escape(doc, quote=True)
    return f"<iframe srcdoc=\"{safe}\" style=\"width:100%;height:820px;border:1px solid #E5E8EE;border-radius:10px\"></iframe>"

def _load_ledger_dict():
    if not os.path.exists(LEDGER_PATH):
        return {}
    with open(LEDGER_PATH, encoding="utf-8") as f:
        return json.load(f)


def make_excel():
    led = _load_ledger_dict()
    if not led:
        return None
    return export_excel(led, "pmo_action_tracker.xlsx")


def make_word():
    led = _load_ledger_dict()
    if not led:
        return None
    return export_word(led, "pmo_status_report.docx")

def read_image(path):
    if not path:
        return gr.update(), "⚠️ Upload an image first."
    try:
        text = transcribe_image(path)       
    except Exception as e:
        return gr.update(), f"Couldn't read the image: {e}"
    if not text.strip():
        return gr.update(), "Couldn't find readable text in that image."
    return text, "📝 Transcribed into the notes box — check it, fix any OCR slips, then Generate draft."


def generate_draft(notes):
    if not notes or not notes.strip():
        empty = pd.DataFrame(columns=ACTION_COLS)
        return (gr.update(visible=False), "⚠️ Paste some meeting notes first.",
                empty, pd.DataFrame(columns=RISK_COLS), pd.DataFrame(columns=DECISION_COLS),
                pd.DataFrame(columns=STATUS_COLS), "", "")
    try:
        me = extract(notes)          # real Groq call
    except Exception as e:
        empty = pd.DataFrame(columns=ACTION_COLS)
        return (gr.update(visible=False), f"❌ Extraction failed: {e}",
                empty, pd.DataFrame(columns=RISK_COLS), pd.DataFrame(columns=DECISION_COLS),
                pd.DataFrame(columns=STATUS_COLS), "", "")
    a, r, d, s = _me_to_frames(me)
    msg = (f"✅ Draft ready — {len(a)} actions, {len(r)} risks, {len(d)} decisions. "
           "Review and edit below, then approve.")
    return (gr.update(visible=True), msg, a, r, d, s,
            me.meta.project_name or "", me.meta.meeting_date or "")


def approve(project_name, meeting_date, a, r, d, s):
    try:
        me = _frames_to_me(project_name, meeting_date, a, r, d, s)
    except Exception as e:
        return f"❌ Could not read the edited tables: {e}", _dashboard_iframe()
    ledger = ProjectLedger.load(LEDGER_PATH)
    commit_meeting(ledger, me)       
    ledger.save(LEDGER_PATH)
    return "✅ Approved and added to the project. Dashboard updated below.", _dashboard_iframe()


def reset_project():
    for p in (LEDGER_PATH, "dashboard.html"):
        if os.path.exists(p):
            os.remove(p)
    return "🗑️ Project cleared.", _dashboard_iframe()


def chat_fn(message, history):
    history = history or []
    if not message or not message.strip():
        return history, "", _dashboard_iframe()
    led = {}
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, encoding="utf-8") as f:
            led = json.load(f)
    try:
        resp = respond(message, led)            
        if resp.is_edit and resp.operations:
            ledger = ProjectLedger.load(LEDGER_PATH)
            changes = apply_edits(ledger, resp.operations)
            ledger.save(LEDGER_PATH)
            reply = resp.reply or ("Done — " + "; ".join(changes))
        else:
            reply = resp.reply or "(no answer)"
    except Exception as e:
        reply = f"Sorry — I hit an error: {e}"
    history = history + [{"role": "user", "content": message},
                         {"role": "assistant", "content": reply}]
    return history, "", _dashboard_iframe()          


def build_app():
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="indigo"), title="PMO Copilot") as demo:
        gr.Markdown("# PMO Copilot\n*Drop meeting notes → review the AI's draft → approve into your project.*")

        with gr.Row():
            with gr.Column(scale=3):
                notes = gr.Textbox(label="Meeting notes", lines=10, value=SAMPLE,
                                   placeholder="Paste meeting notes here…")
                with gr.Accordion("📷 Or upload a photo of handwritten notes", open=False):
                    note_img = gr.Image(label="Handwritten notes", type="filepath", height=200)
                    ocr_btn = gr.Button("Read image → notes", variant="secondary")
            with gr.Column(scale=1):
                gen_btn = gr.Button("Generate draft", variant="primary")
                reset_btn = gr.Button("Clear project", variant="secondary")
        status = gr.Markdown("")

        with gr.Group(visible=False) as draft_group:
            gr.Markdown("### Review the draft — edit any cell, then approve")
            with gr.Row():
                proj = gr.Textbox(label="Project", scale=2)
                mdate = gr.Textbox(label="Meeting date", scale=1)
            gr.Markdown("**Action items**")
            actions = gr.Dataframe(headers=ACTION_COLS, col_count=(len(ACTION_COLS), "fixed"),
                                   interactive=True, wrap=True)
            gr.Markdown("**Risks**")
            risks = gr.Dataframe(headers=RISK_COLS, col_count=(len(RISK_COLS), "fixed"),
                                 interactive=True, wrap=True)
            gr.Markdown("**Decisions**")
            decisions = gr.Dataframe(headers=DECISION_COLS, col_count=(len(DECISION_COLS), "fixed"),
                                     interactive=True, wrap=True)
            gr.Markdown("**Status updates**")
            statuses = gr.Dataframe(headers=STATUS_COLS, col_count=(len(STATUS_COLS), "fixed"),
                                    interactive=True, wrap=True)
            approve_btn = gr.Button("Approve & add to project", variant="primary")

        gr.Markdown("## Project dashboard")
        dash = gr.HTML(_dashboard_iframe())

        gr.Markdown("## Export to Microsoft 365")
        gr.Markdown("*Same ledger, as the files PMs circulate — an Excel tracker and a Word status report.*")
        with gr.Row():
            xlsx_btn = gr.Button("Generate Excel (tracker + registers)")
            docx_btn = gr.Button("Generate Word (status report)")
        with gr.Row():
            xlsx_file = gr.File(label="Excel", interactive=False)
            docx_file = gr.File(label="Word", interactive=False)

        gr.Markdown("## Ask or instruct the assistant")
        gr.Markdown("*Ask: \"What's blocking the claims-scoring model?\", \"Summarise status for leadership.\"  ·  "
                    "Instruct: \"Mark ACT-002 as done\", \"Add a risk about vendor delay\", \"Change ACT-001 owner to Priya.\"*")
        chatbot = gr.Chatbot(height=340, show_label=False)
        with gr.Row():
            chat_msg = gr.Textbox(placeholder="Ask about the project…", scale=5, show_label=False)
            chat_send = gr.Button("Send", variant="primary", scale=1)

        ocr_btn.click(read_image, [note_img], [notes, status])
        xlsx_btn.click(make_excel, None, xlsx_file)
        docx_btn.click(make_word, None, docx_file)
        gen_btn.click(generate_draft, [notes],
                      [draft_group, status, actions, risks, decisions, statuses, proj, mdate])
        approve_btn.click(approve, [proj, mdate, actions, risks, decisions, statuses],
                          [status, dash])
        reset_btn.click(reset_project, None, [status, dash])
        chat_send.click(chat_fn, [chat_msg, chatbot], [chatbot, chat_msg, dash])
        chat_msg.submit(chat_fn, [chat_msg, chatbot], [chatbot, chat_msg, dash])
    return demo


if __name__ == "__main__":
    build_app().launch(inbrowser=True)
