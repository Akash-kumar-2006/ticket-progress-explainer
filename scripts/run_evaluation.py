"""Run the synthetic evaluation and print the metric summary.

Usage:
  python -m scripts.run_evaluation
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal, create_all
from backend.app.services.evaluation_service import EvaluationService


def main() -> None:
    create_all()
    db = SessionLocal()
    try:
        svc = EvaluationService(db)
        result = svc.run()
        print("Evaluation complete (synthetic reviewer rules).")
        for key, value in result["metrics"].items():
            print(f"  {key}: {value}")
        print(f"Cases: {result['num_cases']}")
        print("Results stored in experiment_runs and evaluation_results tables.")
    finally:
        db.close()


if __name__ == "__main__":
    main()