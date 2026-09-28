"""Read-only next-action measurement probe.

Scores every evaluation case with the *same* scorer the real evaluation uses
(``EvaluationService._score_case``) but never writes to the database or the CSV,
so it is safe to run at any time to compare before/after a change.

Usage: python -m scripts.measure_next_action
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.app.database import SessionLocal
from backend.app.services.evaluation_service import (
    EVALUATION_CSV,
    EvaluationService,
    _aggregate,
)


def main() -> None:
    cases = pd.read_csv(EVALUATION_CSV, keep_default_na=False).to_dict(orient="records")
    db = SessionLocal()
    try:
        svc = EvaluationService(db)
        results = [svc._score_case(case) for case in cases]
    finally:
        db.close()

    m = _aggregate(results)
    scored = [r for r in results if r["expected_state"] != "RESOLVED"]
    category_scored = [r for r in scored if r["next_action_category_scored"]]

    print(f"cases: {len(results)}   next-action cases: {len(scored)}   category-scored: {len(category_scored)}")
    print(f"next_action_accuracy        : {m['next_action_accuracy']}")
    print(f"next_action_category_accuracy: {m['next_action_category_accuracy']} (n={m['next_action_category_scored_cases']})")
    print(f"next_action_text_match_rate : {m['next_action_text_match_rate']}")
    print(f"state {m['state_accuracy']}  blocker {m['blocker_accuracy']}  date {m['promised_date_accuracy']}  grounding {m['grounding_accuracy']}")
    print(f"understanding {m['baseline_mean_understanding']} -> {m['prototype_mean_understanding']}")

    print("\ncategory mismatches:")
    for r in category_scored:
        if not r["next_action_match"]:
            print(f"  {r['case_id']} {r['ticket_id']:<10} expected={r['expected_action_category']:<20} got={r['next_action_category'] or '-'}")


if __name__ == "__main__":
    main()
