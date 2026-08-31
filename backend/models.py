"""
Database models for the Payment Recovery Agent.

Payment      -> one row per failed payment we're trying to recover
AuditLog     -> one row per action the agent takes on a payment (append-only)
"""
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recovery.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    razorpay_payment_id = Column(String, unique=True, index=True)
    razorpay_order_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)          # in rupees
    currency = Column(String, default="INR")
    customer_email = Column(String, nullable=True)
    customer_contact = Column(String, nullable=True)
    instrument_fingerprint = Column(String, nullable=True, index=True)  # proxy for "same card/UPI ID"

    # Raw failure info straight from Razorpay
    error_code = Column(String, nullable=True)        # e.g. BAD_REQUEST_ERROR
    error_reason = Column(String, nullable=True)       # e.g. payment_failed
    error_description = Column(String, nullable=True)  # free-text description

    # Set by the root-cause classifier
    root_cause = Column(String, nullable=True)   # insufficient_funds | issuer_decline |
                                                  # otp_timeout | risk_block | network_timeout |
                                                  # expired_instrument | unknown
    root_cause_confidence = Column(Float, nullable=True)
    root_cause_explanation = Column(String, nullable=True)  # Gemini's plain-language reasoning

    # Set by the recovery decision engine / executor
    recovery_action = Column(String, nullable=True)     # retry | alt_method_link | nudge | escalate | no_action
    recovery_status = Column(String, default="pending")  # pending | in_progress | recovered | failed | skipped
    recovered_amount = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    audit_logs = relationship("AuditLog", back_populates="payment", cascade="all, delete-orphan")


class AuditLog(Base):
    """
    Append-only record of every decision/action the agent takes.
    This is the artifact that proves the system is 'explainable, bounded and gated'.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)

    actor = Column(String, nullable=False)       # "rule_engine" | "gemini" | "system"
    action = Column(String, nullable=False)      # classify | decide | execute_retry | execute_nudge | escalate | stop
    detail = Column(String, nullable=True)        # human-readable explanation
    outcome = Column(String, nullable=True)        # success | failure | skipped
    was_bounded_by_rule = Column(Boolean, default=False)  # True if a stopping rule prevented an action

    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    payment = relationship("Payment", back_populates="audit_logs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
