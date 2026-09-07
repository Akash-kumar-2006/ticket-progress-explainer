"""Cross-platform setup: install backend deps, generate+validate data, create
evaluation cases, seed the database, install frontend dependencies.

Usage:
  python -m scripts.setup
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd or ROOT)


def main() -> None:
    print("=== Installing backend requirements ===")
    run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

    from scripts import generate_dataset, generate_evaluation_cases, seed_database, validate_dataset

    print("=== Generating synthetic dataset ===")
    generate_dataset.main()
    print("=== Validating dataset ===")
    validate_dataset.run()
    print("=== Building evaluation cases ===")
    generate_evaluation_cases.main()
    print("=== Seeding database ===")
    print(seed_database.seed())

    if (ROOT / "frontend" / "package.json").exists():
        print("=== Installing frontend dependencies ===")
        run(["npm", "install"], cwd=ROOT / "frontend")

    print("""
Setup complete.
  Backend : cd backend && uvicorn app.main:app --reload
  Frontend: cd frontend && npm run dev
  Tests   : python -m pytest -q
  Eval    : python -m scripts.run_evaluation
""")


if __name__ == "__main__":
    main()