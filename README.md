# Payment Recovery Agent
**Track 03 — AI Revenue Recovery (Razorpay AI Buildathon 2026)**

Detects why a payment failed, decides a bounded recovery action, executes it,
and reports measured recovery across a batch — with a full audit trail.

## Architecture

```
Failed payment (Razorpay test-mode / synthetic batch)
        │
        ▼
Root-cause classifier   (rules on error_code, Gemini for ambiguous cases)
        │
        ▼
Recovery decision engine  (explicit, inspectable rule table — not a black box)
        │
        ▼
Executor  (retry / alt-method link / nudge / escalate-only)
        │        │
        ▼        ▼
  Audit trail   Stopping rules (max retries, never retry risk_block)
        │
        ▼
Batch metrics  (recovery rate, ₹ recovered, breakdown, honest exception list)
```

## Status

- [x] Step 1 — Database models + Razorpay test client + synthetic failure batch generator
- [x] Step 2 — Root-cause classifier (rules layer + Gemini fallback)
- [x] Step 3 — Recovery decision engine (deterministic table + retry-cap + risk_block safety floor)
- [x] Step 4 — Executor + audit trail wiring
- [x] Step 5 — Stopping rules (retry cap + risk_block floor + instrument-level dedup)
- [x] Step 6 — Batch runner + metrics (single pipeline call + shared metrics module)
- [x] Step 7a — React dashboard (backend-connected, verified builds cleanly)
- [ ] Step 7b — Deploy backend (Render) + frontend (Vercel), record pitch video

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows CMD
pip install -r requirements.txt

copy .env.example .env
# fill in RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET (TEST MODE ONLY — starts with rzp_test_)
# fill in GEMINI_API_KEY (reuse the OKGIP/UFDR-INTEL key, model = gemini-2.5-flash-lite)

python seed_failures.py     # generates 60 synthetic failed payments
python main.py               # starts API on http://localhost:8000
```

**Fastest way to see the whole thing work (this is your demo path):**
```bash
python pipeline.py
```
Runs classify -> decide -> execute against whatever's in `recovery.db` and
prints the full JSON result (per-stage summaries + final metrics) straight
to the terminal. Or hit the same thing over HTTP once `main.py` is running:
```bash
curl -X POST http://localhost:8000/pipeline/run
```

The step-by-step calls below still work individually if you want to inspect
the batch at each stage rather than running it all at once.

Classify the seeded batch:
```bash
curl -X POST http://localhost:8000/payments/classify-batch
```
This runs every pending payment through the rule layer first, falling back to
Gemini only for cases the keyword rules can't confidently match. Check
`GET /payments/{id}/audit` on a few records to see which layer (`rule_engine`
vs `gemini`) made each call and why — that's your audit trail evidence for
the pitch.

Decide recovery actions:
```bash
curl -X POST http://localhost:8000/payments/decide-batch
```
Deterministic lookup from `root_cause` to a bounded action (see the table in
`decision_engine.py`). `risk_block` is hard-coded to always escalate — this
can't be overridden by editing the table by mistake, since there's a separate
`NEVER_AUTO_CONTACT` safety check. Retries that would exceed `MAX_RETRY_ATTEMPTS`
are automatically downgraded to `escalate` instead of looping.

Execute the batch:
```bash
curl -X POST http://localhost:8000/payments/execute-batch
```
`retry`/`alt_method_link` create a **real** Razorpay test-mode order (proves
genuine API integration). `nudge` drafts a **real** Hinglish reminder via
Gemini. `escalate` takes no automated action — it just logs to a human queue
and is never counted as recovered.

**Be upfront in the pitch:** whether the *customer* completes the recovered
checkout is simulated (weighted random per action type — see
`executor.SIMULATED_SUCCESS_RATES`), since there's no live customer in a
hackathon batch run to drive a real payment to completion. The API calls
(order creation, Gemini drafting) are real; the human-completion step is
honestly modeled, not measured. Say this out loud rather than letting the
metrics imply otherwise — that honesty is explicitly part of the bar.

Check final numbers:
```bash
curl http://localhost:8000/metrics
```

> If you already ran an earlier version of this project and have an existing
> `recovery.db`, delete it before re-seeding — the schema changed (added
> `instrument_fingerprint`) and SQLite won't auto-migrate.

## Frontend (dashboard)

```bash
cd frontend
npm install
copy .env.example .env
# defaults to http://localhost:8000 — fine for local dev, change for deploy
npm run dev
```
Opens on `http://localhost:5173`. Make sure the backend (`python main.py`) is
running first — the dashboard fetches `/payments` and `/metrics` on load and
does nothing useful without it.

Click **Run pipeline** in the top-right to trigger classify → decide →
execute against whatever's currently in the database, then watch the ledger
tape, metrics, root-cause bars, and table populate live. Click any row to
open the audit trail drawer.

**Design direction**: a dark financial-terminal "recovery console" — the live
scrolling ledger tape at the top is the signature element (a ledger is
literally what a revenue-recovery system produces), monospace type for
anything that's data (IDs, amounts, timestamps), geometric sans for
headings/labels. Respects `prefers-reduced-motion`.

## Deploying

- **Backend** → Render: point it at `backend/`, set the same env vars as
  `.env`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **Frontend** → Vercel: point it at `frontend/`, set `VITE_API_URL` to your
  deployed Render backend URL in Vercel's environment variables.
- Update `allow_origins` in `main.py` from `["*"]` to your actual Vercel URL
  before the final submission — the wildcard is fine for local dev only.

## Why some failures are synthetic, not live API calls

Razorpay's test mode only has dedicated test cards for a few failure classes
(insufficient funds, generic issuer decline, expired card — see
`razorpay_client.py::TEST_FAILURE_INSTRUMENTS`). There's no documented way to
force a risk-engine block or a raw network timeout through the test API.
`seed_failures.py` generates those as synthetic rows with realistic
`error_code`/`error_description` shapes, clearly labeled as such. **Be upfront
about this in the pitch** — the bar rewards honesty over a demo that pretends
every row came from a live API call.

## Root-cause buckets

| Bucket | Example trigger | Recovery action |
|---|---|---|
| `insufficient_funds` | Card declined, low balance | Nudge (wait + reminder), not retry |
| `issuer_decline` | Bank declined the transaction | Alt-method checkout link |
| `otp_timeout` | Customer didn't complete 3DS/OTP in time | Retry (same instrument, fresh session) |
| `network_timeout` | Gateway/bank didn't respond | Retry with backoff |
| `expired_instrument` | Card expired | Alt-method checkout link |
| `risk_block` | Risk engine flagged the transaction | **Escalate only — never retry** |

## Stopping rules (non-negotiable)

- **Retry cap**: max `MAX_RETRY_ATTEMPTS` (default 2, in `.env`) per payment — beyond that, auto-downgraded to `escalate`
- **`risk_block` floor**: never auto-retried or auto-nudged, hard-coded separately from the lookup table so it can't be broken by editing the table
- **Instrument-level dedup**: if the same card/UPI instrument (`instrument_fingerprint`) already has another payment being contacted (retry/alt_method_link/nudge) in the same run, further payments on that instrument are downgraded to `escalate` — this stops the agent from sending a customer three simultaneous recovery messages for three different failed payments. The seed script assigns instruments from a pool of ~35 across the 60 payments specifically so this rule has something to trigger on — check the audit trail (`was_bounded_by_rule=True` entries) to see it firing.
