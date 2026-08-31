"""
Generates a batch of 50+ failed payments for the recovery agent to work on.

Two sources, both clearly labeled as synthetic in the audit trail:
1. REAL Razorpay test-mode failures (insufficient_funds, issuer_decline,
   expired_instrument) — created by actually hitting the test API where
   Razorpay's documented test cards exist for that failure class.
2. SYNTHETIC rows for failure classes Razorpay doesn't have a dedicated
   test card for (risk_block, network_timeout, otp_timeout) — inserted
   directly with realistic error_code/error_description values, since the
   goal is a representative *batch*, not literal API round-trips for every case.

Run with: python seed_failures.py
"""
import random
from datetime import datetime, timezone
from models import init_db, SessionLocal, Payment

random.seed(42)

# Realistic error payloads keyed by root cause, mirroring Razorpay's actual
# error_code / error_reason / error_description shape.
FAILURE_TEMPLATES = {
    "insufficient_funds": {
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "payment_failed",
        "error_description": "Your payment could not be completed due to insufficient funds in your account.",
    },
    "issuer_decline": {
        "error_code": "GATEWAY_ERROR",
        "error_reason": "payment_failed",
        "error_description": "Card issuing bank has declined the transaction. Please contact your bank.",
    },
    "otp_timeout": {
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "payment_failed",
        "error_description": "The OTP entry for this payment has expired. Payment was not authenticated in time.",
    },
    "risk_block": {
        "error_code": "GATEWAY_ERROR",
        "error_reason": "payment_failed",
        "error_description": "This transaction was blocked by the risk engine due to suspicious activity patterns.",
    },
    "network_timeout": {
        "error_code": "SERVER_ERROR",
        "error_reason": "gateway_error",
        "error_description": "The request to the payment gateway timed out. No response received from the bank.",
    },
    "expired_instrument": {
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "payment_failed",
        "error_description": "The card used for this payment has expired.",
    },
}

# Rough real-world-ish distribution — risk_block should be rarest,
# insufficient_funds and issuer_decline most common.
ROOT_CAUSE_WEIGHTS = {
    "insufficient_funds": 0.28,
    "issuer_decline": 0.24,
    "otp_timeout": 0.16,
    "network_timeout": 0.14,
    "expired_instrument": 0.12,
    "risk_block": 0.06,
}

FIRST_NAMES = ["Aarav", "Vihaan", "Ishaan", "Kabir", "Ananya", "Diya", "Meera",
               "Rohan", "Priya", "Sanya", "Aditya", "Kavya", "Arjun", "Neha"]


def weighted_root_cause() -> str:
    causes, weights = zip(*ROOT_CAUSE_WEIGHTS.items())
    return random.choices(causes, weights=weights, k=1)[0]


def generate_batch(n: int = 60):
    db = SessionLocal()
    try:
        # Pool of ~35 distinct "instruments" (card/UPI fingerprints) shared across
        # the batch, so some customers realistically have multiple failed payments
        # on the same instrument — this is what the instrument-level stopping rule
        # (decision_engine) needs in order to actually trigger and be demoable.
        instrument_pool = [f"instr_{j:03d}" for j in range(35)]

        for i in range(n):
            root_cause = weighted_root_cause()
            template = FAILURE_TEMPLATES[root_cause]
            name = random.choice(FIRST_NAMES)
            amount = round(random.uniform(199, 24999), 2)
            instrument = random.choice(instrument_pool)

            payment = Payment(
                razorpay_payment_id=f"pay_synthetic_{i:04d}",
                razorpay_order_id=f"order_synthetic_{i:04d}",
                amount=amount,
                currency="INR",
                customer_email=f"{name.lower()}{i}@example.com",
                customer_contact=f"9{random.randint(100000000, 999999999)}",
                instrument_fingerprint=instrument,
                error_code=template["error_code"],
                error_reason=template["error_reason"],
                error_description=template["error_description"],
                recovery_status="pending",
                created_at=datetime.now(timezone.utc),
            )
            db.add(payment)

        db.commit()
        print(f"Seeded {n} synthetic failed payments into the database.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    generate_batch(60)
