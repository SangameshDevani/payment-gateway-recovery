"""
Ties the three stages together into one call: classify -> decide -> execute.
This is what you actually demo — one button/one command that runs the whole
batch and prints the final measured numbers.
"""
from classifier import classify_batch
from decision_engine import decide_batch
from executor import execute_batch
from metrics import compute_metrics


def run_full_pipeline(db) -> dict:
    classify_summary = classify_batch(db)
    decide_summary = decide_batch(db)
    execute_summary = execute_batch(db)
    final_metrics = compute_metrics(db)

    return {
        "classify": classify_summary,
        "decide": decide_summary,
        "execute": execute_summary,
        "metrics": final_metrics,
    }


if __name__ == "__main__":
    # CLI entry point: `python pipeline.py` runs the whole batch against
    # whatever's currently in recovery.db (run seed_failures.py first).
    from models import init_db, SessionLocal
    import json

    init_db()
    db = SessionLocal()
    try:
        result = run_full_pipeline(db)
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()
