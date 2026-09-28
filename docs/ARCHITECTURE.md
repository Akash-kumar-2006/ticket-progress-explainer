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
- Any event cited by the next-action claim is guaranteed to appear in the
  selected set, even when a newer event of the same type won the per-category
  slot, so a grounded sentence always points at something the reviewer can see.

### 5a. Action-marker lexicon (`engines/action_markers.py`)
- Maps lowercase marker phrases found in real event text to one of eleven action
  categories (approval, vendor response, customer response, escalation,
  reassignment, verification, deployment, information, investigation, follow-up,
  closure), each with a fixed customer-facing template.
- Category order is explicit and significant: `VERIFICATION` is evaluated before
  `DEPLOYMENT` so "verify the fix once deployed" is a verification step.
- Only the most recent matching event is used, and events before the last
  resolution or reopen are ignored.
- Returns a signal carrying the text, the source `event_id`, the category and a
  confidence level (`specific` / `generic` / `sparse`).
- Sparse evidence: with no marker it returns `None` and the caller keeps its
  state-specific sentence; with a single unmarked event it returns a safe
  `STATUS_CONFIRMATION`; with no events at all the state engine states no
  action whatsoever. Full rationale in `NEXT_ACTION.md`.

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
  annotates the evaluation CSV with scores. Next action is scored on its
  **category** against a structurally derived reference label
  (`scripts/generate_evaluation_cases.py`), not on string identity.
- `services/ingestion.py`: normalizes raw rows → ORM objects; detects duplicates
  and out-of-order; safely parses metadata JSON.
- `services/grounding_gate.py`: validation layer around **any** generator.
  Verifies that every claim cites a real event of that ticket, that the text
  invents no completion, date, approval, vendor response or customer contact,
  and that a refusal is used when evidence is insufficient. `assert_grounded()`
  raises so tests and CI fail on a violation. The optional LLM generator is
  validated by exactly this gate and stays optional.
- `services/human_evaluation_service.py`: builds a blank reviewer packet, records
  reviewer judgements, and computes acceptance rate, next-action agreement and
  inter-reviewer agreement (Cohen's kappa for two reviewers, Fleiss' kappa for
  three or more) in plain Python. Ships with **no** review rows; the summary
  reports `validation_completed: false` until real reviewers submit.

## API layer (`api/routes.py`)

Role gates are enforced server-side by `enforce_role()`:
- Roles must belong to the fixed ticket-support vocabulary
  (`CUSTOMER`, `SUPPORT_AGENT`, `AGENT`, `REVIEWER`, `ADMIN`, `SYSTEM`);
  anything else is rejected with 400.
- If an `X-Role` header is present it must agree with the body role (403
  otherwise), so a request body cannot claim more privilege than the header.
- `ReviewRequest` / `PublishRequest` / `RollbackRequest` have **no default
  role**: omitting it is a validation error, not a silent grant of privilege.
- generate → `SYSTEM` (or any actor) creates a DRAFT.
- review → `REVIEWER`/`ADMIN`; first approve → PENDING_REVIEW, second → APPROVED; REJECT → REJECTED.
- publish → `REVIEWER`/`ADMIN`, requires APPROVED.
- rollback → `ADMIN` only, requires PUBLISHED, restores a target version content as a new version.

Every mutation is audited (actor, role, old ➝ new, reason). Frontend visibility
is never treated as a security control. See `SECURITY.md`.

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