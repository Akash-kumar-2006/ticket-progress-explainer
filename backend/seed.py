"""Run the full pipeline: generate dataset -> validate -> create evaluation
cases -> seed database. Equivalent to scripts/setup.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import generate_dataset, generate_evaluation_cases, seed_database, validate_dataset


def main() -> None:
    print("=== 1/4 Generating synthetic dataset ===")
    generate_dataset.main()
    print("=== 2/4 Validating dataset ===")
    validate_dataset.run()
    print("=== 3/4 Building evaluation cases ===")
    generate_evaluation_cases.main()
    print("=== 4/4 Seeding database ===")
    print(seed_database.seed())


if __name__ == "__main__":
    main()