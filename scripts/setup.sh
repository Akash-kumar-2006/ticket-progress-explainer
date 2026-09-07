#!/usr/bin/env bash
# Unix/Linux/macOS setup script.
set -euo pipefail

echo "=== Creating virtual environment ==="
if [ ! -d "backend/.venv" ]; then
    python3 -m venv backend/.venv
fi

PY="backend/.venv/bin/python"
echo "=== Installing backend requirements ==="
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r backend/requirements.txt

echo "=== Generating dataset, validating, evaluating cases, seeding DB ==="
"$PY" -m scripts.setup

echo
echo "Setup complete."
echo "Run backend :  cd backend && ../.venv/bin/uvicorn app.main:app --reload"
echo "Run frontend:  cd frontend && npm run dev"
echo "Tests       :  cd backend && ../backend/.venv/bin/python -m pytest -q"
echo "Evaluation  :  backend/.venv/bin/python -m scripts.run_evaluation"