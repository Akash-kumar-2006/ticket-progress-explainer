# Requirements

## 1. Problem statement

Regional support transfers (e.g. NA → India → Vendor Operations) create long,
opaque tickets. Customers asked "what's happening?" receive either a raw status
string or a bland auto-reply. This project provides a **generated, evidence-aware
progress explanation** that says *why* the ticket is where it is, *what* it is
waiting on, and *when* it might be done — without inventing facts.

## 2. Functional requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Ingest ticket + event data and rebuild a clean chronological timeline. |
| FR-2 | Flag data anomalies: duplicate event IDs, out-of-order timestamps, status conflicts (e.g. RESOLVED → IN_PROGRESS). |
| FR-3 | Detect dependencies: approvals, vendor requests, customer waits, internal tasks; track pending/completed/blocked. |
| FR-4 | Derive a transparent progress state (SCHEDULED, WAITING_FOR_APPROVAL, WAITING_FOR_VENDOR, BLOCKED, DELAYED, INVESTIGATING, REOPENED, RESOLVED, …) from explicit, documented rules. |
| FR-5 | Compute a promised-date status (ON_TRACK / AT_RISK / OVERDUE / COMPLETED), never claiming AT_RISK/OVERDUE without cause. |
| FR-6 | Select the minimal relevant evidence events per claim. |
| FR-7 | Generate a customer-facing explanation where every sentence carries supporting evidence IDs. |
| FR-8 | Suppress any claim with no supporting evidence; fall back to an explicit uncertainty statement. |
| FR-9 | Compute a Grounding Score (0–100) with a human-readable breakdown. |
| FR-10 | Persist each explanation with versioning; support review → publish → rollback. |
| FR-11 | Record every action in an audit trail (actor, role, old/new value, reason). |
| FR-12 | Provide a dashboard for tickets, explanations, dependencies, evaluation and audit. |
| FR-13 | Run a baseline-vs-prototype evaluation over a curated case set. |
| FR-14 | Provide an offline ticketing stub with stable return contracts for later real integrations. |

## 3. Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | **Reproducibility** — dataset generation, validation and evaluation must be reproducible (seed 42). |
| NFR-2 | **Actionability** — the state, the waiting reason and the next action are immediately readable by a customer. |
| NFR-3 | **Anti-hallucination** — no claim is emitted without at least one referenced event. |
| NFR-4 | **Explainability** — the grounding score must be decomposable into its own reasons. |
| NFR-5 | **Auditability** — every lifecycle mutation leaves an immutable audit row. |
| NFR-6 | **Offline-first** — no external network or credentials required for the full feature set. |
| NFR-7 | **Performance** — explanation generation must complete in well under a second per ticket on a laptop. |
| NFR-8 | **Determinism** — same data + same rules ⇒ same output (no randomness in state/event selection). |
| NFR-9 | **Privacy** — the stub and guidance minimize PII; see docs/PRIVACY.md. |

## 4. Acceptance criteria (demo check-list)

1. `python -m scripts.setup` completes end-to-end: 119 tickets, 1021 events imported, 1 duplicate skipped.
2. `python -m pytest` passes (47 tests).
3. Seven demo tickets produce the seven expected scenarios (see README table).
4. The frontend renders dashboard, ticket detail with generated explanation + evidence, evaluation screen, audit.
5. Review/publish/rollback is blocked for insufficient roles and audited.
6. A first-run user can follow the 30–45 min evaluation script without external credentials.
7. All claims in every generated explanation reference existing events; conflict and insufficiency cases are explicitly surfaced, never silently resolved.
8. Frontend `npm run build` passes; the built SPA is served from FastAPI at `/`.