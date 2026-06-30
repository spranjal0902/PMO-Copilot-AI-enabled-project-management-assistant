# PMO Copilot

**AI-Enabled Project Management Assistant** — turns raw meeting notes (typed or a photo of
handwritten ones) into structured PMO artifacts, tracks them *across* meetings, and exposes
a review-and-approve web UI with a grounded Q&A + editing chat. Built with a compliance lens
for regulated domains (insurance / finance).

The point isn't to *summarise* a meeting. It's to maintain a living project: an action
opened in week 1, blocked in week 2, and closed in week 3 is **one tracked item with a
history** — not three disconnected rows.

## The loop

```
 photo of notes ──(vision OCR)──┐
                                ▼
 typed notes ─────────────►  extract  ──►  reconcile  ──►  ProjectLedger  ──►  dashboard (HTML)
                            (LLM, JSON     (cross-meeting    (persistent          │
                             + schema       entity linking)   project state)      └──►  ask / edit chat
                             validation)         ▲                                      (grounded in ledger)
                                                 │
                                    human reviews & edits the draft
                                        before it's committed
```

Drop notes → AI drafts the artifacts → **you edit them in tables** → approve into the
project → ask it questions or instruct edits in plain English.

## What's in the box

- **Cross-meeting tracking** — a reconciliation step links "same item, different wording" by
  meaning, so the project state stays de-duplicated as meetings accumulate.
- **Human-in-the-loop** — extraction (draft) is split from commit (approve). The model
  *proposes*; a person disposes. Nothing reaches the project state unreviewed.
- **Grounded Q&A** — ask "what's blocking the model?" or "summarise for leadership" and get
  answers built only from the ledger, with item ids and dates cited. No vector DB: the whole
  project fits in context, so retrieval is trivial.
- **Conversational editing** — "mark ACT-002 done", "add a risk about vendor delay". The LLM
  interprets the request into *typed operations*; code applies them deterministically.
- **Compliance lens** — risks/decisions touching regulation, data protection, or audit are
  flagged and surfaced separately on the dashboard.
- **Photo intake** — upload handwritten notes; a vision model transcribes them into the notes
  box, where OCR slips get caught at the same review step everything else uses.
- **Microsoft 365 export** — one click renders the same ledger as an Excel tracker (action /
  risk / decision / status sheets) and a Word status report for circulation. Same source of
  truth as the dashboard, so the numbers always agree.

## Design decisions

- **The Pydantic schema is the single source of truth.** Every artifact is a typed model;
  enums force a controlled vocabulary, which is what makes the output chartable.
- **JSON mode + schema validation, not constrained decoding.** Model output is treated as
  untrusted input and validated at the boundary — robust across SDK/model changes.
- **The LLM call is isolated in one swappable function.** Ports-and-adapters: the provider or
  model can change without touching pipeline logic.
- **The model proposes, code disposes.** Edits and commits are deterministic typed operations,
  never free-form mutation of state — the same discipline applied to the approve gate and the
  edit chat.
- **RAG in spirit, not in infrastructure.** Grounded answers without an embedding store,
  because the corpus is small enough to fit in context — knowing *when not* to add machinery.

## Project structure

```
app/
  schema.py       Pydantic data contract (the single source of truth)
  prompts.py      extraction system prompt + one worked example
  groq_client.py  the isolated LLM calls (JSON / text / vision) with retry + backoff
  extractor.py    transcript → validated MeetingExtraction
  reconcile.py    generic cross-meeting record linker
  store.py        ProjectLedger — persistent project state (JSON)
  pipeline.py     extract → reconcile → commit
  qa.py           grounded question-answering over the ledger
  assistant.py    unified chat: answer a question OR apply typed edits
  vision.py       photo → transcribed text (downscale + vision OCR)
  export_office.py  ledger → Excel tracker (.xlsx) + Word status report (.docx)
app_web.py        Gradio app: drop/upload → draft → edit → approve → dashboard + chat + export
build_dashboard.py  stdlib-only ledger → self-contained dashboard.html
demo_multi.py     ingest 3 sample meetings end-to-end (CLI)
run_extract.py    single-meeting extraction (CLI)
docs/             business case (time-saved model) and supporting material
samples/          fictional multi-week project for the demo
tests/            offline tests (stub LLMs — no network, no quota)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your key into .env
export GROQ_API_KEY=$(grep -v '^#' .env | cut -d= -f2)
# (a free key: https://console.groq.com/keys)
```

## Run

```bash
python app_web.py             # the full web app (recommended)
python demo_multi.py          # CLI: ingest 3 sample meetings and print the ledger

# offline tests — stubbed LLMs, no network or quota
PYTHONPATH=. python tests/test_pipeline.py
PYTHONPATH=. python tests/test_crossmeeting.py
PYTHONPATH=. python tests/test_workstream.py
```

## Tech stack

Python · Pydantic (schema + validation) · Groq (LLM inference, OpenAI-compatible) ·
Gradio (web UI) · Pillow (image prep) · openpyxl + python-docx (Microsoft 365 export).
No database; project state is a JSON ledger.

The model ids live as constants in `app/groq_client.py` (one text model, one vision model).
Groq rotates hosted models periodically — if a model is retired, list the live ones with
`curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"` and
swap the constant.

## Limitations / next iteration

- Edits apply immediately with no undo — a production version would add a confirm/undo step.
- Grounded Q&A relies on the project fitting in context; a larger history would need real
  retrieval (embeddings + vector store).
- Handwriting OCR quality varies; the human review step is the mitigation by design.
