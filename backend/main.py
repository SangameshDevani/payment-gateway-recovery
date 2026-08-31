"""
Payment Recovery Agent — FastAPI backend.

Step 1 of the build (this file): expose the failed-payment batch and basic
CRUD so the frontend + classifier/decision-engine (steps 2-3) have something
to work against. Root-cause classification and recovery execution are added
in later modules (classifier.py, recovery_engine.py — not yet built).
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import init_db, get_db, Payment, AuditLog
from seed_failures import generate_batch
from classifier import classify_batch, classify_payment
from decision_engine import decide_batch, decide_action
from executor import execute_batch, execute_action
from pipeline import run_full_pipeline
from metrics import compute_metrics

app = FastAPI(title="Payment Recovery Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before you ship the real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    # Render's free tier resets the disk on every cold start (after the
    # service spins down from inactivity), which wipes SQLite. Auto-seed on
    # boot if the table is empty so the demo always has data without needing
    # shell access to run seed_failures.py manually.
    from models import SessionLocal
    db = SessionLocal()
    try:
        existing_count = db.query(Payment).count()
        if existing_count == 0:
            generate_batch(60)
            print("Startup: database was empty, auto-seeded 60 synthetic failed payments.")
        else:
            print(f"Startup: database already has {existing_count} payments, skipping auto-seed.")
    finally:
        db.close()


@app.post("/admin/reseed")
def reseed_database(db: Session = Depends(get_db)):
    """
    Wipes all payments/audit logs and seeds a fresh batch of 60. Useful for
    getting a clean batch right before a demo, since Render's free tier
    doesn't give shell access to run seed_failures.py directly.
    """
    db.query(AuditLog).delete()
    db.query(Payment).delete()
    db.commit()
    generate_batch(60)
    return {"status": "reseeded", "count": 60}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/payments")
def list_payments(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.recovery_status == status)
    payments = query.order_by(Payment.created_at.desc()).all()
    return payments


@app.get("/payments/{payment_id}")
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@app.get("/payments/{payment_id}/audit")
def get_payment_audit(payment_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.payment_id == payment_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    return logs


@app.post("/payments/classify-batch")
def run_batch_classification(db: Session = Depends(get_db)):
    """
    Classifies every unclassified payment (rule layer first, Gemini fallback
    for anything the rules can't confidently bucket). Idempotent — already
    classified payments are skipped.
    """
    summary = classify_batch(db)
    return summary


@app.post("/payments/{payment_id}/classify")
def classify_single_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    classify_payment(payment, db)
    db.commit()
    db.refresh(payment)
    return payment


@app.post("/payments/decide-batch")
def run_batch_decisions(db: Session = Depends(get_db)):
    """
    Runs the recovery decision engine on every classified payment that
    doesn't have an action yet. Deterministic — same root_cause always
    produces the same action (see decision_engine.DECISION_TABLE).
    """
    summary = decide_batch(db)
    return summary


@app.post("/payments/{payment_id}/decide")
def decide_single_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not payment.root_cause:
        raise HTTPException(status_code=400, detail="Payment has no root_cause yet — classify it first")

    decide_action(payment, db)
    db.commit()
    db.refresh(payment)
    return payment


@app.post("/payments/execute-batch")
def run_batch_execution(db: Session = Depends(get_db)):
    """
    Executes every payment that has a decided action and is still 'pending'.
    retry/alt_method_link create a real Razorpay test-mode order; nudge drafts
    a real Gemini message; escalate takes no automated action. Customer
    completion is simulated for retry/alt_method_link/nudge — see executor.py
    docstring for why, and be upfront about this in the pitch.
    """
    summary = execute_batch(db)
    return summary


@app.post("/payments/{payment_id}/execute")
def execute_single_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not payment.recovery_action:
        raise HTTPException(status_code=400, detail="Payment has no recovery_action yet — decide it first")

    execute_action(payment, db)
    db.commit()
    db.refresh(payment)
    return payment


@app.post("/pipeline/run")
def run_pipeline(db: Session = Depends(get_db)):
    """
    THE endpoint for the demo: runs classify -> decide -> execute on the
    whole batch in one call and returns per-stage summaries plus final
    metrics. Idempotent-ish — already-classified/decided/executed payments
    are skipped by each stage, so re-running is safe (it just processes
    whatever's still pending).
    """
    return run_full_pipeline(db)


@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """
    Batch-level metrics: the numbers the Buildathon bar explicitly asks for
    (measured money recovered, honest exception list, breakdown by cause).
    """
    return compute_metrics(db)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)