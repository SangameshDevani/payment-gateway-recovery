"""
Recovery decision engine.

Deliberately NOT an LLM call. The Buildathon bar asks for "every money action
explainable, bounded and gated" — the way you prove that is by making the
decision a plain lookup table a human can read in five seconds, not a prompt
an LLM might interpret differently each run.

Gemini is used upstream (classifier.py) to figure out WHY a payment failed.
This module decides WHAT TO DO about it, deterministically.
"""
import os
from dotenv import load_dotenv

from models import Payment, AuditLog

load_dotenv()

MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", 2))

# The core decision table. Read this in the pitch — it's the whole point.
#
# root_cause          -> action
# ---------------------------------------------------------------
# insufficient_funds  -> nudge            (don't retry the same card immediately —
#                                           remind the customer, let balance top up)
# issuer_decline      -> alt_method_link  (retrying the same card is pointless —
#                                           offer a different payment method)
# otp_timeout         -> retry            (transient — customer likely just ran
#                                           out of time, a fresh session usually works)
# network_timeout     -> retry            (transient — gateway/bank-side hiccup)
# expired_instrument  -> alt_method_link  (card is dead, no retry will ever work)
# risk_block          -> escalate         (NEVER auto-retry or auto-nudge a fraud
#                                           block — human review only)
# unknown             -> escalate         (safe default when classification failed)
DECISION_TABLE = {
    "insufficient_funds": "nudge",
    "issuer_decline": "alt_method_link",
    "otp_timeout": "retry",
    "network_timeout": "retry",
    "expired_instrument": "alt_method_link",
    "risk_block": "escalate",
    "unknown": "escalate",
}

# Root causes that must NEVER be auto-retried or auto-nudged, under any
# circumstances, even if the table above is edited by mistake later.
# This is the hard-coded safety floor, separate from the lookup table.
NEVER_AUTO_CONTACT = {"risk_block"}


def _instrument_already_being_contacted(payment: Payment, db) -> bool:
    """
    Instrument-level stopping rule: if the same card/UPI instrument already
    has another payment in this run decided as retry/alt_method_link/nudge,
    don't also auto-contact this one. Prevents the agent from hammering the
    same customer with multiple simultaneous recovery attempts across their
    different failed payments.
    """
    if not payment.instrument_fingerprint:
        return False

    sibling = (
        db.query(Payment)
        .filter(Payment.instrument_fingerprint == payment.instrument_fingerprint)
        .filter(Payment.id != payment.id)
        .filter(Payment.recovery_action.in_(["retry", "alt_method_link", "nudge"]))
        .first()
    )
    return sibling is not None


def decide_action(payment: Payment, db) -> Payment:
    """
    Looks up the bounded action for this payment's root cause, applies the
    retry-cap and instrument-level stopping rules, and writes an audit log
    explaining the decision. Caller is responsible for db.commit().
    """
    root_cause = payment.root_cause or "unknown"
    action = DECISION_TABLE.get(root_cause, "escalate")

    was_bounded = False
    detail = f"root_cause='{root_cause}' -> action='{action}' via decision table."

    # Hard safety floor: risk_block can never resolve to retry/nudge, no matter what.
    if root_cause in NEVER_AUTO_CONTACT and action in ("retry", "nudge"):
        action = "escalate"
        was_bounded = True
        detail = f"root_cause='{root_cause}' is in NEVER_AUTO_CONTACT — forced to 'escalate' regardless of table."

    # Retry cap stopping rule: if this would be a retry but we're already at
    # the cap, downgrade to escalate instead of looping forever.
    if action == "retry" and payment.retry_count >= MAX_RETRY_ATTEMPTS:
        action = "escalate"
        was_bounded = True
        detail = (
            f"root_cause='{root_cause}' would retry, but retry_count "
            f"({payment.retry_count}) >= MAX_RETRY_ATTEMPTS ({MAX_RETRY_ATTEMPTS}). "
            f"Downgraded to 'escalate' to avoid an unbounded retry loop."
        )

    # Instrument-level stopping rule: same card/UPI already being contacted
    # via another payment in this run — don't pile on with a second contact.
    if action in ("retry", "alt_method_link", "nudge") and _instrument_already_being_contacted(payment, db):
        action = "escalate"
        was_bounded = True
        detail = (
            f"Instrument '{payment.instrument_fingerprint}' already has another payment "
            f"being contacted (retry/alt_method_link/nudge) in this run. Downgraded to "
            f"'escalate' to avoid contacting the same customer/instrument multiple times at once."
        )

    payment.recovery_action = action

    log = AuditLog(
        payment_id=payment.id,
        actor="decision_engine",
        action="decide",
        detail=detail,
        outcome="success",
        was_bounded_by_rule=was_bounded,
    )
    db.add(log)
    db.flush()  # make this decision visible to the instrument-check for the next payment in the batch

    return payment


def decide_batch(db) -> dict:
    """
    Decides an action for every classified payment that doesn't have one yet.
    Returns a count of decisions made per action, for a quick sanity check.
    """
    pending = (
        db.query(Payment)
        .filter(Payment.root_cause.isnot(None))
        .filter(Payment.recovery_action.is_(None))
        .all()
    )

    summary = {}
    for payment in pending:
        decide_action(payment, db)
        summary[payment.recovery_action] = summary.get(payment.recovery_action, 0) + 1

    db.commit()
    summary["total_decided"] = len(pending)
    return summary
