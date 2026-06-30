# PMO Copilot — AI-Enabled Project Management Assistant

Turns raw meeting notes into structured PMO artifacts (action tracker, risk register,
decision log, status report) and **tracks them across meetings**, so an action opened in
week 1 and closed in week 3 is one item with a history — not three disconnected rows.
Includes a compliance lens that flags risks/decisions touching regulation, data
protection, or audit (built for regulated industries like insurance/finance).

## Architecture (one line per piece)

- `app/schema.py` — Pydantic data contract. Single source of truth for every artifact.
- `app/prompts.py` — extraction system prompt + one worked example.
- `app/extractor.py` — single-meeting: transcript → validated `MeetingExtraction`.
- `app/groq_client.py` — the one isolated LLM call (Groq, JSON mode, retry/backoff).
- `app/reconcile.py` — cross-meeting record linking (is this new item the same as an open one?).
- `app/store.py` — `ProjectLedger`: persistent project state across meetings (JSON).
- `app/pipeline.py` — `ingest_meeting()`: extract → reconcile → update ledger.
- `demo_multi.py` — run the whole thing over the 3 sample meetings, live.

Both LLM steps use **Groq** (free, no card, EU-friendly; model `llama-3.3-70b-versatile`)
in JSON mode, validated by Pydantic. The model call is isolated in one function
(`app/groq_client.py`), so swapping in another provider is a one-line change.

## Run it for real (5 minutes)

1. **Get a free Groq key** at https://console.groq.com (no credit card needed)

2. **Set up the environment** (from the project folder):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   export GROQ_API_KEY=your_key_here                    # Windows: set GROQ_API_KEY=your_key_here
   ```

3. **Single meeting:**
   ```bash
   python run_extract.py samples/sample_transcript.txt
   ```
   You'll see a real Groq extraction — the four artifacts as JSON.

4. **Cross-meeting tracking (the headline feature):**
   ```bash
   python demo_multi.py
   ```
   Ingests three weekly meetings of "Project Helios" in order. Watch the
   training-rerun action go open → blocked → done as ONE tracked item, and the
   GDPR compliance risk get carried across and closed.

5. **Try your own meetings:** drop `.txt` notes in `samples/`, point `demo_multi.py`
   at them, rerun. The ledger (`project_ledger.json`) persists between runs.

## Test without a key (verifies the plumbing)

```bash
python -m tests.test_pipeline        # single-meeting contract
python -m tests.test_crossmeeting    # cross-meeting merge logic
```
These inject a stand-in model, so they prove schema/parsing/merge logic without
network. The real runs above use live Groq.

## Limitations

Extraction is high-recall, not perfect, on long rambling notes (each item keeps a
`source_quote` for traceability). The compliance flag surfaces items for human review —
it is not a legal judgment. Reconciliation is conservative and can occasionally miss a
re-worded match; a human edit step (future scope) covers that. JSON-file persistence is
demo-grade; production wants a database.

## Future scope

Human-in-the-loop edit/approve before artifacts finalize; a real database + multi-project
support; write-back to Microsoft 365 / Power BI instead of the local visualization layer;
per-extraction confidence scores routing low-confidence items to review; and an evaluation
harness scoring extraction quality against a labelled set.
