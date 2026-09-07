# Windows PowerShell setup script.
# Creates a virtual environment, installs backend + frontend dependencies,
# generates the synthetic dataset, initializes and seeds the database.

$ErrorActionPreference = "Stop"

Write-Host "=== Creating virtual environment ==="
if (-not (Test-Path "backend\.venv")) {
    python -m venv backend\.venv
}

$Py = "backend\.venv\Scripts\python.exe"
Write-Host "=== Installing backend requirements ==="
& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements.txt

Write-Host "=== Generating dataset, validating, evaluating cases, seeding DB ==="
& $Py -m scripts.setup

Write-Host "`nSetup complete."
Write-Host "Run backend :  cd backend ; ..\backend\.venv\Scripts\uvicorn app.main:app --reload"
Write-Host "Run frontend:  cd frontend ; npm run dev"
Write-Host "Tests       :  python -m pytest -q"
Write-Host "Evaluation  :  backend\.venv\Scripts\python -m scripts.run_evaluation"