.PHONY: setup dataset seed backend frontend test eval run clean

PYTHON ?= python

setup:
	$(PYTHON) -m scripts.setup

dataset:
	$(PYTHON) -m scripts.generate_dataset

seed:
	$(PYTHON) -m scripts.seed_database

backend:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

test:
	$(PYTHON) -m pytest -q

eval:
	$(PYTHON) -m scripts.run_evaluation

run: setup backend

clean:
	rm -f ticket_progress.db
	rm -rf data/raw data/processed data/evaluation backend/__pycache__

# On Windows PowerShell use `scripts/setup.ps1` or `python scripts/setup.py`