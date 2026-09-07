# Ticket Progress Explanation Generator

An **evidence-grounded** system that generates customer-facing progress
explanations for support tickets that are transferred between regional teams.
It produces a short message ("waiting on vendor approval", "blocked", "delayed",
"resolved") where **every sentence cites the exact ticket events that support
it**. When the evidence is insufficient, it says so — it never invents facts.

```
                +--------------------------------------------------------------+
                |  Ticket events (status, notes, transfers, approvals,        |
                |  vendor updates, promised dates)                             |
                +------------------------------------+-------------------------+
                                                     |
                          +--------------------------v--------------------------+
                          |                E N G I N E   S T A C K             |
                          |  Timeline  ->  Dependency  ->  Progress state      |
                          |  Date risk  ->  Evidence     ->  Grounding score   |
                          +--------------------------+-------------------------+
                                                     |
                                                     v
                          +--------------------------+--------------------------+
                          |  RULE-BASED GENERATOR (default) / status baseline  |
                          |  claims, each backed by evidence IDs; unsupported  |
                          |  claims are dropped or replaced by uncertainty     |
                          +--------------------------+--------------------------+
                                                     |
                          +--------------------------v--------------------------+
                          |  FastAPI  (/api/*)  <->  React dashboard (Vite)    |
                          |  review -> publish -> rollback, full audit trail    |
                          +-----------------------------------------------------+
```

The full pipeline runs **offline on synthetic, reproducible data (seed 42)** —
no external credentials are required. A stub ticketing integration keeps the
same return contracts, so a real system (ServiceNow/Jira) can be plugged in
without changing the engines.

## Why this project exists (problem)

- Support tickets get transferred between regional teams. Customers see a bare
  status or nothing at all, and keep asking "what's happening?".
- Status alone is misleading: a ticket may be `IN_PROGRESS` while the real
  cause is a pending security approval, an awaited vendor part, or a missed
  promise date.
- Naive auto-replies risk **hallucinating** facts the data does not support.
  For a customer-facing channel, an invented "resolved" or invented reason is
  worse than saying "we can't reliably say".

## What it does (approach)

1. Rebuilds a clean event timeline, flagging duplicates, out-of-order records
   and status conflicts.
2. Tracks the dependency chain (approvals, vendors, customers, internal tasks).
3. Derives a **transparent progress state** and a **promised-date status**
   from explicit rules.
4. Selects the relevant events as **evidence** and composes sentences where
   each claim carries its evidence IDs.
5. Computes a **grounding score (0–100)** with a human-readable breakdown.
6. Stores every generated explanation with **versioning, review, publish and
   rollback workflows**, and a full **audit trail**.
7. Runs a **baseline vs prototype evaluation** over 64 curated cases.

## Tech stack

| Layer      | Technology |
|------------|------------|
| Backend    | Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite |
| Frontend   | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Axios |
| Testing    | pytest (47 tests) |
| Data       | Pandas, synthetic generator (seed 42, reproducible) |

## Repository layout

```
backend/app/
  api/           REST endpoints (routes, enums, schemas)
  engines/       timeline, dependency, state, date_risk, evidence, grounding
  generators/    base, rule-based (default), baseline (status-only), llm (optional)
  services/      explanation orchestration, evaluation, ingestion, validation
  integrations/  offline ticketing stub (ServiceNow-like)
  models/        SQLAlchemy models (tickets, events, explanations, audit, evaluation)
scripts/         dataset generation, validation, evaluation cases, seeding
data/            synthetic raw/processed datasets + evaluation cases (reproducible)
frontend/        React/Vite dashboard
tests/           pytest suite
docs/            requirements, architecture, privacy, change control, evaluation
```

## Quick start

Prerequisites: Python 3.11+ and Node 18+.

```bash
# 1. Install Python dependencies (a requirements.txt or your env manager)
pip install -r requirements.txt

# 2. Generate + validate + seed (idempotent)
python -m scripts.setup          # runs generate_dataset, validate, eval-cases, seed

# 3. Backend API
cd backend
uvicorn app.main:app --reload     # http://127.0.0.1:8000  (OpenAPI at /docs)

# 4. Frontend (development)
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies /api)

# OR single-server production demo: build the frontend, then serve from FastAPI
cd frontend && npm run build
# restart uvicorn -> the SPA is served at http://127.0.0.1:8000/
```

Run the test suite at any time:

```bash
python -m pytest          # 47 tests: engines, generators, evaluation, API, role gates
```

## Demo tickets

Open these in the Ticket Explorer (or call the API):

| Ticket     | Scenario                                    |
|------------|---------------------------------------------|
| DEMO-001   | Scheduled work, on track                    |
| DEMO-002   | Waiting on an approval                      |
| DEMO-003   | Waiting on a vendor, at risk                |
| DEMO-004   | Overdue / delayed                           |
| DEMO-005   | Status conflict (RESOLVED → IN_PROGRESS)    |
| DEMO-006   | Insufficient evidence (safety-net output)   |
| DEMO-007   | Reopened ticket                             |

## Evaluation summary (synthetic, deterministic reviewer rules)

Baseline = status-only. Prototype = evidence-grounded. Over 64 cases:

| Metric                          | Baseline | Prototype |
|---------------------------------|----------|-----------|
| Understanding (0–5)             | 2.34     | 4.36      |
| Follow-up required              | 57.8%    | 26.6%     |
| State accuracy                  | —        | 76.6%     |
| Blocker accuracy                | —        | 79.2%     |
| Promised-date accuracy          | —        | 96.9%     |
| Grounding ≥ 60                  | —        | 85.9%     |

See [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md) for the full write-up.

## Documentation

- [Requirements & acceptance criteria](docs/REQUIREMENTS.md)
- [Architecture & rule catalog](docs/ARCHITECTURE.md)
- [Privacy & data handling](docs/PRIVACY.md)
- [Change control & review workflow](docs/CHANGE_CONTROL.md)
- [Error analysis & edge cases](docs/ERROR_ANALYSIS.md)
- [Known limitations](docs/LIMITATIONS.md)
- [API reference](docs/API.md)
- [Validation methodology](docs/VALIDATION.md)
- [30–45 min evaluation demo script](docs/DEMO_SCRIPT.md)

## License

MIT — see [LICENSE](LICENSE).