"""
Thin wrapper around the Razorpay Python SDK, scoped to test mode only.

Docs: https://razorpay.com/docs/payments/payments/test-card-upi-details/
"""
import os
import razorpay
from dotenv import load_dotenv

load_dotenv()

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    raise RuntimeError(
        "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set. "
        "Copy .env.example to .env and fill in your TEST MODE keys "
        "(Dashboard > Settings > API Keys > Test Mode)."
    )

if not KEY_ID.startswith("rzp_test_"):
    raise RuntimeError(
        "Refusing to run: RAZORPAY_KEY_ID does not look like a test-mode key "
        "(should start with 'rzp_test_'). This project must never touch live keys."
    )

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))


def create_order(amount_rupees: float, receipt: str, currency: str = "INR") -> dict:
    """Create a Razorpay order to attach a payment attempt to."""
    return client.order.create({
        "amount": int(amount_rupees * 100),  # paise
        "currency": currency,
        "receipt": receipt,
        "payment_capture": 1,
    })


def fetch_payment(payment_id: str) -> dict:
    """Fetch full payment details, including error_code/error_description if failed."""
    return client.payment.fetch(payment_id)


def create_recovery_order(original_payment: dict, receipt_suffix: str = "recovery") -> dict:
    """
    Create a fresh order for a recovery checkout link, so the customer can
    retry payment without us ever touching card data directly.
    """
    return create_order(
        amount_rupees=original_payment["amount"] / 100,
        receipt=f"{original_payment.get('order_id', 'order')}-{receipt_suffix}",
    )


# Known Razorpay test instruments that trigger specific failure classes.
# Use these when generating the synthetic failure batch (see seed_failures.py).
# Reference: https://razorpay.com/docs/payments/payments/test-card-upi-details/
TEST_FAILURE_INSTRUMENTS = {
    "insufficient_funds": {
        "card_number": "4000000000000002",
        "note": "Simulates a card decline due to insufficient funds.",
    },
    "issuer_decline": {
        "card_number": "4000000000000010",
        "note": "Simulates a generic issuer/bank decline.",
    },
    "expired_instrument": {
        "card_number": "4111111111111111",
        "card_expiry": "01/20",  # deliberately expired
        "note": "Simulates an expired card.",
    },
    # For risk_block / network_timeout / otp_timeout: Razorpay doesn't expose
    # dedicated test cards for all of these, so simulate them by writing directly
    # into the Payment table with the corresponding error_code/error_description
    # (see seed_failures.py). Document this clearly in the README as synthetic data.
}
