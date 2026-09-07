# Final report

## Executive summary

Tickets transferred between regional support teams leave customers blind:
raw statuses ("IN_PROGRESS") hide the real reasons (approval stuck, vendor part,
missed promise date). This project builds a **rule-based, evidence-grounded
explanation generator** that tells the customer *what is happening, why, and
what happens next* — with every sentence tied to the exact ticket event that
supports it, and with an explicit "not enough information" fallback instead of
invented facts.

It runs fully offline on reproducible synthetic data, exposes the entire logic
as auditable, explainable components (state, dependency, date-risk, groundingscoring), wraps generation in a review→publish→rollback lifecycle with an audit
trail, and provides a React dashboard plus an evaluation harness that compares
the prototype against a status-only baseline.

## Results (synthetic evaluation, deterministic reviewer rules)

64 cases · baseline = status-only · prototype = evidence-grounded

| Metric | Baseline | Prototype | Δ |
|--------|----------|-----------|---|
| Customer understanding (0–5) | 2.344 | 4.359 | **+86.0%** |
| Follow-up required rate | 57.8% | 26.6% | **−54.1%** |
| Progress-state accuracy | — | 76.6% | — |
| Blocker / waiter accuracy | — | 79.2% | — |
| Next-action accuracy | — | 48.6% | — |
| Promised-date accuracy | — | 96.9% | — |
| Explanations with grounding ≥ 60 | — | 85.9% | — |

Interpretation:
- The explanation **reduces customers' need to follow up** by more than half
  versus a bare status.
- The strongest, most trustworthy wins are the **blocker/waiter** and
  **promised-date** accuracy (looking at *which team/person/vendor* is the wait
  and *whether the date is still achievable*).
- Next-action accuracy is lowest — the system is honest about it (prediction on
  sparse evidence; see LIMITATIONS.md).

## Quality gates

| Gate | Result |
|------|--------|
| Dataset validation | 119 tickets, 1022 events, 0 ticket issues; 4 deliberate event edge cases documented |
| Unit/API test suite | 47/47 passing (`python -m pytest`) |
| Frontend build | `npm run build` clean (TypeScript strict) |
| Single-server demo | FastAPI serves SPA + `/api` from one process |
| Determinism | seed 42; fixed reference date; identical outputs across runs |

## What was built

**Backend (FastAPI + SQLAlchemy, `backend/`)**
- Engines: timeline, dependency, progress-state (documented rule order), date-risk,
  evidence selection, grounding score.
- Generators: baseline (control), rule-based (default, anti-hallucination guards),
  llm (optional, unused by default); factory-selected.
- Services: explanation orchestration, evaluation, ingestion/validation.
- Lifecycle: DRAFT → review → publish → rollback + full audit trail; role gates.
- Stub ticketing integration with stable contracts.

**Frontend (React + Vite + TS, `frontend/`)**
- Dashboard (states, regions, priority, grounding), Ticket Explorer + detail
  (explanation, claims↔evidence, timeline, dependencies, versions, audit),
  Evaluation dashboard (charts, per-case table), Documentation.
- Served in one process after `npm run build`.

**Data & scripts (`data/`, `scripts/`)**
- Reproducible generator (seed 42), validator, evaluation-case builder, seeder,
  evaluation runner, one-shot setup.

**Docs (`docs/`)**
- Requirements, architecture, privacy, change control, error analysis,
  limitations, API, validation, this report, demo script.

## How the goals map

| Requirement | Evidence |
|-------------|----------|
| Evidence-grounded output | every claim carries evidence IDs; tests enforce it |
| Honest handling of bad data | conflict banner (DEMO-005), uncertainty fallback (DEMO-006) |
| Beats baseline | +86% understanding, −54% follow-ups in the experiment |
| Works offline | full stack runs on synthetic data, zero credentials |
| Explainable & auditable | grounding breakdown + audit trail + version history |

## Next steps

1. Real ticketing backend behind the identified `fetch_*` contracts.
2. Human evaluation panel for limited cases; keep deterministic reviewer independent.
3. LLM generator behind factory + grounding/refusal test gate (optional).
4. PostgreSQL + IdP-backed roles for production.
5. Broaden next-action phrasing with a richer action-marker catalog to lift the
   weakest metric.