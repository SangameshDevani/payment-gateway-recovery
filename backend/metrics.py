"""
Batch-level metrics. Pulled out into its own module so both the standalone
/metrics endpoint and the end-to-end pipeline runner return the exact same
numbers, computed the same way — no risk of the two drifting apart.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Payment


def compute_metrics(db: Session) -> dict:
    total = db.query(func.count(Payment.id)).scalar() or 0
    recovered = db.query(func.count(Payment.id)).filter(
        Payment.recovery_status == "recovered"
    ).scalar() or 0
    failed = db.query(func.count(Payment.id)).filter(
        Payment.recovery_status == "failed"
    ).scalar() or 0
    escalated = db.query(func.count(Payment.id)).filter(
        Payment.recovery_status == "escalated"
    ).scalar() or 0
    total_amount = db.query(func.sum(Payment.amount)).scalar() or 0
    recovered_amount = db.query(func.sum(Payment.recovered_amount)).scalar() or 0

    by_cause = (
        db.query(Payment.root_cause, func.count(Payment.id))
        .group_by(Payment.root_cause)
        .all()
    )

    by_action = (
        db.query(Payment.recovery_action, func.count(Payment.id))
        .group_by(Payment.recovery_action)
        .all()
    )

    bounded_count = (
        db.query(func.count(func.distinct(Payment.id)))
        .filter(Payment.audit_logs.any(was_bounded_by_rule=True))
        .scalar() or 0
    )

    # Honest exception list — every payment actioned but not recovered.
    exceptions = (
        db.query(Payment)
        .filter(Payment.recovery_status.in_(["failed", "escalated"]))
        .all()
    )

    return {
        "total_payments": total,
        "recovered_count": recovered,
        "failed_count": failed,
        "escalated_count": escalated,
        "pending_count": total - recovered - failed - escalated,
        "recovery_rate_pct": round((recovered / total * 100), 2) if total else 0,
        "total_amount_at_risk": round(total_amount, 2),
        "total_amount_recovered": round(recovered_amount, 2),
        "breakdown_by_root_cause": {cause or "unclassified": count for cause, count in by_cause},
        "breakdown_by_action": {action or "undecided": count for action, count in by_action},
        "payments_bounded_by_stopping_rules": bounded_count,
        "exception_count": len(exceptions),
        "exception_payment_ids": [p.id for p in exceptions],
    }
