"""
Root-cause classifier.

Two layers, in order:
1. RULE LAYER — matches Razorpay's structured error_code/error_reason plus
   keyword matching on error_description. Fast, free, fully deterministic.
   Handles the majority of cases since Razorpay's error descriptions are
   fairly consistent per failure class.
2. GEMINI FALLBACK — only invoked when the rule layer can't confidently
   match a bucket (free-text description, unfamiliar error_code combo).
   Uses the same OpenAI-compatible endpoint pattern as OKGIP/UFDR-INTEL.

Every classification — rule-based or Gemini — writes an AuditLog row, so the
audit trail shows exactly which layer made the call and why. This is what
makes the "root cause" step inspectable rather than a black box.
"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from models import Payment, AuditLog

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Gemini's OpenAI-compatible endpoint — same pattern used in OKGIP/UFDR-INTEL
_gemini_client = None
if GEMINI_API_KEY:
    _gemini_client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

VALID_ROOT_CAUSES = [
    "insufficient_funds",
    "issuer_decline",
    "otp_timeout",
    "risk_block",
    "network_timeout",
    "expired_instrument",
]

# Keyword rules, checked against error_description (lowercased).
# Order matters — more specific phrases first.
RULES = [
    ("risk_block", ["risk engine", "blocked", "suspicious activity", "fraud"]),
    ("otp_timeout", ["otp", "authentication", "expired in time", "not authenticated"]),
    ("insufficient_funds", ["insufficient funds", "low balance", "insufficient balance"]),
    ("expired_instrument", ["card has expired", "card expired", "expired card"]),
    ("network_timeout", ["timed out", "timeout", "no response received", "gateway did not respond"]),
    ("issuer_decline", ["declined the transaction", "bank has declined", "issuing bank"]),
]


def _rule_based_classify(payment: Payment):
    """Returns (root_cause, confidence, explanation) or None if no rule matched."""
    description = (payment.error_description or "").lower()

    for root_cause, keywords in RULES:
        if any(kw in description for kw in keywords):
            explanation = (
                f"Matched keyword rule for '{root_cause}' in error_description: "
                f"\"{payment.error_description}\""
            )
            return root_cause, 0.95, explanation

    return None


def _gemini_classify(payment: Payment):
    """
    Fallback classifier for cases the rule layer couldn't confidently match.
    Asks Gemini to pick one of VALID_ROOT_CAUSES and explain briefly.
    Returns (root_cause, confidence, explanation).
    """
    if _gemini_client is None:
        # No API key configured — fail safe to 'unknown' rather than crash.
        return "unknown", 0.0, "Gemini not configured (GEMINI_API_KEY missing); rule layer found no match."

    prompt = f"""A payment failed on Razorpay with the following details:

error_code: {payment.error_code}
error_reason: {payment.error_reason}
error_description: {payment.error_description}
amount: {payment.amount} INR

Classify the root cause into EXACTLY ONE of these buckets:
{", ".join(VALID_ROOT_CAUSES)}

Respond ONLY with JSON, no markdown, no preamble, in this exact shape:
{{"root_cause": "<one of the buckets above>", "confidence": <float 0-1>, "explanation": "<one sentence, plain language>"}}
"""

    try:
        response = _gemini_client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        root_cause = parsed.get("root_cause")
        if root_cause not in VALID_ROOT_CAUSES:
            root_cause = "unknown"

        return root_cause, float(parsed.get("confidence", 0.5)), parsed.get("explanation", "")

    except Exception as e:
        # Never let a malformed LLM response break the pipeline — fail to 'unknown'
        # and record the failure honestly in the explanation.
        return "unknown", 0.0, f"Gemini classification failed: {e}"


def classify_payment(payment: Payment, db) -> Payment:
    """
    Classifies a single payment, updates it in place, and writes an audit log.
    Caller is responsible for db.commit().
    """
    rule_result = _rule_based_classify(payment)

    if rule_result:
        root_cause, confidence, explanation = rule_result
        actor = "rule_engine"
    else:
        root_cause, confidence, explanation = _gemini_classify(payment)
        actor = "gemini"

    payment.root_cause = root_cause
    payment.root_cause_confidence = confidence
    payment.root_cause_explanation = explanation

    log = AuditLog(
        payment_id=payment.id,
        actor=actor,
        action="classify",
        detail=explanation,
        outcome="success" if root_cause != "unknown" else "failure",
    )
    db.add(log)

    return payment


def classify_batch(db) -> dict:
    """Classifies every payment with no root_cause set yet. Returns a summary count."""
    pending = db.query(Payment).filter(Payment.root_cause.is_(None)).all()

    summary = {"rule_engine": 0, "gemini": 0, "unknown": 0}
    for payment in pending:
        classify_payment(payment, db)
        if payment.root_cause == "unknown":
            summary["unknown"] += 1
        elif payment.root_cause_explanation and payment.root_cause_explanation.startswith("Matched keyword"):
            summary["rule_engine"] += 1
        else:
            summary["gemini"] += 1

    db.commit()
    summary["total_classified"] = len(pending)
    return summary
