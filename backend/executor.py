"""
Executor.

Turns a decided recovery_action into an actual (or honestly-simulated) step:

- retry / alt_method_link -> creates a REAL Razorpay test-mode order for a
                              fresh checkout session (proves genuine API
                              integration, not a mock), then simulates
                              whether the customer completes it — there's no
                              live customer in a hackathon batch run to drive
                              a real checkout to completion.
- nudge                    -> drafts a REAL Hinglish reminder via Gemini
                              (logged, not actually sent — no SMS/WhatsApp
                              gateway wired up), then simulates completion.
- escalate                 -> no automated action at all. Logged to a human
                              queue. NEVER simulated as recovered — this is
                              the honest exception list the bar asks for.

Every execution writes an audit log with outcome + amount, and updates the
Payment row's status for this pass.

IMPORTANT FOR THE PITCH: be upfront that customer completion is simulated,
not measured from real users. The Razorpay order creation itself is real;
whether a human would have paid is not something a hackathon batch can prove.
"""
import random
from dotenv import load_dotenv

from models import Payment, AuditLog
import razorpay_client
from classifier import _gemini_client, GEMINI_MODEL  # reuse the same configured Gemini client

load_dotenv()

random.seed(7)

# Simulated completion odds per action. These reflect a plausible ordering
# (a same-card retry recovers more often than a cold nudge) but are NOT
# measured production numbers — document this honestly in the pitch.
SIMULATED_SUCCESS_RATES = {
    "retry": 0.55,
    "alt_method_link": 0.42,
    "nudge": 0.30,
}


def _draft_hinglish_nudge(payment: Payment) -> str:
    """Real Gemini call to draft a short Hinglish reminder. Never actually sent anywhere."""
    if _gemini_client is None:
        return f"[Gemini not configured] Aapka payment of Rs.{payment.amount:.0f} pending hai, please retry."

    prompt = (
        f"Write a short, friendly Hinglish (Hindi+English mix, Roman script) SMS reminder "
        f"for a customer whose payment of Rs.{payment.amount:.0f} failed. "
        f"Ask them to complete the payment again. Keep it under 30 words. "
        f"Reply with ONLY the message text, nothing else."
    )
    try:
        response = _gemini_client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Gemini draft failed: {e}] Aapka payment pending hai, please retry."


def _attempt_checkout_recovery(payment: Payment, action: str) -> tuple[bool, str]:
    """
    Creates a real Razorpay test-mode order for the recovery attempt, then
    simulates whether the customer completed it. Returns (succeeded, detail).
    """
    try:
        order = razorpay_client.create_order(
            amount_rupees=payment.amount,
            receipt=f"{payment.razorpay_payment_id}-{action}",
        )
        order_id = order.get("id", "unknown")
    except Exception as e:
        return False, f"Razorpay order creation failed: {e}"

    success_rate = SIMULATED_SUCCESS_RATES.get(action, 0.4)
    succeeded = random.random() < success_rate

    detail = (
        f"Created real Razorpay recovery order {order_id} for Rs.{payment.amount:.2f}. "
        f"Customer completion SIMULATED (no live customer in this batch run): "
        f"{'completed' if succeeded else 'did not complete'} (simulated odds={success_rate})."
    )
    return succeeded, detail


def execute_action(payment: Payment, db) -> Payment:
    """
    Executes payment.recovery_action, updates status/recovered_amount/retry_count,
    and writes an audit log. Caller is responsible for db.commit().
    """
    action = payment.recovery_action

    if action in ("retry", "alt_method_link"):
        succeeded, detail = _attempt_checkout_recovery(payment, action)
        payment.retry_count += 1
        payment.recovery_status = "recovered" if succeeded else "failed"
        if succeeded:
            payment.recovered_amount = payment.amount
        outcome = "success" if succeeded else "failure"

    elif action == "nudge":
        message = _draft_hinglish_nudge(payment)
        success_rate = SIMULATED_SUCCESS_RATES["nudge"]
        succeeded = random.random() < success_rate
        payment.retry_count += 1
        payment.recovery_status = "recovered" if succeeded else "failed"
        if succeeded:
            payment.recovered_amount = payment.amount
        detail = (
            f'Drafted nudge message: "{message}" '
            f"Customer completion SIMULATED: {'completed' if succeeded else 'did not complete'} "
            f"(odds={success_rate})."
        )
        outcome = "success" if succeeded else "failure"

    elif action == "escalate":
        payment.recovery_status = "escalated"
        detail = "No automated action taken. Escalated to human review queue."
        outcome = "skipped"

    else:
        payment.recovery_status = "failed"
        detail = f"Unknown recovery_action '{action}' — no executor defined for it."
        outcome = "failure"

    log = AuditLog(
        payment_id=payment.id,
        actor="executor",
        action=f"execute_{action}",
        detail=detail,
        outcome=outcome,
    )
    db.add(log)

    return payment


def execute_batch(db) -> dict:
    """Executes every payment that has a decided action but is still 'pending'."""
    pending = (
        db.query(Payment)
        .filter(Payment.recovery_action.isnot(None))
        .filter(Payment.recovery_status == "pending")
        .all()
    )

    summary = {"recovered": 0, "failed": 0, "escalated": 0}
    total_recovered_amount = 0.0

    for payment in pending:
        execute_action(payment, db)
        summary[payment.recovery_status] = summary.get(payment.recovery_status, 0) + 1
        total_recovered_amount += payment.recovered_amount

    db.commit()
    summary["total_executed"] = len(pending)
    summary["total_amount_recovered"] = round(total_recovered_amount, 2)
    return summary
