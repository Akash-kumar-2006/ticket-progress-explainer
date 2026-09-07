# Architecture

## Component overview

```
            ┌────────────────────────────────────────────────────────────┐
            │                     API layer (FastAPI)                    │
            │ /api/tickets, /events, /explanation, /evaluation, …         │
            └───────────────▲──────────────────────┬─────────────────────┘
                            │                      │
                     ┌──────┴──────┐        ┌──────┴──────┐
                     │ Explanation │        │ Evaluation  │
                     │   Service   │        │  Service    │
                     └──────┬──────┘        └──────┬──────┘
                            │                      │
                 ┌──────────▼──────────┐    ┌──────▼──────┐
                 │     ENGINES        │    │ reviewer    │
                 │ (pure functions,   │    │ rules are   │
                 │  pydantic I/O)     │    │ deterministic│
                 │                    │    └─────────────┘
                 │ timeline → deps → │
                 │ state → date risk │
                 │ → evidence →      │
                 │ grounding score   │
                 └──────────┬──────────┘
                            │
                 ┌──────────▼──────────┐
                 │     GENERATORS     │
                 │ baseline (status)  │
                 │ rule_based (default) │
                 │ llm (optional)     │
                 └──────────┬──────────┘
                            │
                 ┌──────────▼──────────┐
                 │   persistence +    │
                 │     audit rows     │
                 └────────────────────┘
```

## Engines — responsibilities and rule order

Everything between the API and the generators is **pure logic over typed
models** (`EventData`, `DependencyInfo`, `ProgressResult`, `ExplanationPayload`),
importable without a database.

### 1. Timeline engine (`engines/timeline.py`)
- Owns the event catalog/titles.
- Detects **duplicate event IDs** (same ID twice, or `is_duplicate` flag),
  **out-of-order timestamps** (a timestamp earlier than a previously-seen one,
  or an `is_out_of_order` flag), and **status conflicts**
  (`RESOLVED` followed later by an unresolved status).
- Returns a chronologically sorted `Timeline` with per-entry flags.

### 2. Dependency engine (`engines/dependency.py`)
- Sources: explicit `DEPENDENCY_CREATED/COMPLETED/BLOCKED` events, approval
  events, vendor updates, and customer-wait markers in work notes.
- Kind resolution (`_kind_from_event`): `approval:*`/`approval_type`, `vendor:*`/
  `vendor`, owner containing "vendor"/"customer", else `internal`.
- Tracks `pending | completed | blocked` and `age_days`.

### 3. Progress-state engine (`engines/state.py`) — rule order (declared order wins)
1. **RESOLVED** — latest valid terminal event is a RESOLUTION or a
   STATUS_CHANGE to RESOLVED.
2. **REOPENED** — a REOPENED event.
3. **WAITING_FOR_APPROVAL** — unresolved approval dependency.
4. **WAITING_FOR_VENDOR / BLOCKED** — unresolved vendor dependency
   (BLOCKED if the dependency is marked blocked).
5. **WAITING_FOR_CUSTOMER** — unresolved customer dependency.
6. **BLOCKED** — any unresolved dependency marked blocked.
7. **WAITING_FOR_INTERNAL_TEAM** — any other unresolved (pending) dependency.
8. **DELAYED** — promised date passed and unresolved, with no active wait.
9. **TRANSFERRED** — regional team transfer within 72h with no activity after.
10. **SCHEDULED** — in progress, latest work note mentions a schedule.
11. **IN_PROGRESS / INVESTIGATING** — by effective status.
- Effective status = latest valid `STATUS_CHANGE`/`RESOLUTION`/`REOPENED`.
- Status conflicts are **remembered as reasons** (surfaced in `payload.conflicts`)
  and reduce the grounding score; they are not silently ignored.

### 4. Date-risk engine (`engines/date_risk.py`)
- `COMPLETED` if resolved.
- `OVERDUE` only when the promised date has passed *and* the ticket is unresolved.
- `AT_RISK` only with evidence: vendor delay hints, or an active waiting state
  within 3 days of the promised date. **Time passing alone is never evidence.**
- `NO_DATE`/`None` when no promised date exists.
- `PROMISED_DATE_CHANGED` driven by genuine schedule change keeps `ON_TRACK`.

### 5. Evidence selector (`engines/evidence.py`)
- Picks one event per expected category (latest status change, latest work note,
  latest transfer, approval activity, vendor update, dependency activity,
  promised-date event, update-to-customer). Deterministic.

### 6. Grounding score (`engines/grounding.py`)
```
score = 100 * (0.40·coverage + 0.10·recency + 0.20·consistency
               + 0.15·dependency_certainty + 0.15·date_certainty)
```
- coverage: how many of 7 expected fact categories have evidence
- recency: latest used event within 30 days
- consistency: 0 when conflicts detected
- dependency certainty & date certainty: clear owner/title / promised date present
- Every weight and the interim numbers are returned in `grounding_breakdown`.

## Generators

- `baseline`: status-only sentence + promised-date completed flag. Used as the
  experimental control.
- `rule_based` (default): composes status, progress/blocker, next-action and
  date paragraphs. Each claim carries evidence IDs; **unsupported claims are
  removed from the output** and, if the status claim is unsupported, replaced by
  an explicit uncertainty sentence (`RuleBasedExplanationGenerator`).
- `llm` (optional): interface reserved for a future model; the system never
  requires it. Factory: `generators/factory.py`.

## Services

- `services/explanation_service.py`: orchestrates engines + generator, persists
  explanations + evidence rows, writes audit rows, computes versions.
- `services/evaluation_service.py`: runs the baseline-vs-prototype experiment
  with a documented deterministic reviewer rule, stores runs + per-case rows,
  annotates the evaluation CSV with scores.
- `services/ingestion.py`: normalizes raw rows → ORM objects; detects duplicates
  and out-of-order; safely parses metadata JSON.

## API layer (`api/routes.py`)

Role gates are enforced on sensitive actions:
- generate → `SYSTEM` (or any actor) creates a DRAFT.
- review → `REVIEWER`/`ADMIN`; first approve → PENDING_REVIEW, second → APPROVED; REJECT → REJECTED.
- publish → `REVIEWER`/`ADMIN`, requires APPROVED.
- rollback → `ADMIN` only, requires PUBLISHED, restores a target version content as a new version.
Every mutation is audited (actor, role, old ➝ new, reason).

## Data model highlights

- `tickets`, `ticket_events` (+ reference tables `regions`, `teams`, `vendors`)
- `generated_explanations` (versioned, status lifecycle) + `explanation_evidence`
- `audit_logs`
- `evaluation_results`, `experiment_runs`

SQLite by default; models are DB-agnostic (set `DATABASE_URL` for PostgreSQL).

## Configuration

`backend/app/config.py` loads `.env`: `DATABASE_URL`, `CORS_ORIGINS`,
`RULES_VERSION`, `MODEL_VERSION`, `REFERENCE_DATE`. All paths that touch files
are anchored to the project root, so the application runs correctly from any
working directory.