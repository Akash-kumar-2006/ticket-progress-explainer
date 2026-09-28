# Validation

## 1. Dataset validation

`scripts/validate_dataset.py` validates the generated dataset against explicit
rules and writes `data/processed/validation_report.json`.

| Check | Level | Result |
|-------|-------|--------|
| missing ticket_id / timestamp | error | 0 |
| invalid event type | error | 0 |
| duplicate event ID | error | 1 (`EV-01020`) |
| future timestamp | error | 0 |
| impossible status transition | error | 3 (`EV-00361`, `EV-00827`, `EV-01007`) |
| malformed date | error | 0 |
| out-of-order timestamp | warning | 1 (`EV-01017`) |

**All are deliberate edge cases** added so the pipeline's tolerance and honesty
can be evaluated. Tickets: 119 ✓ · Events: 1022 checked, 1021 imported
(1 duplicate skipped).

## 2. Product validation (tests)

`python -m pytest` → **155 tests** (47 original + 108 added after review feedback):

| Area | Coverage |
|------|----------|
| Timeline engine | chronological order, duplicate/out-of-order/conflict flags, dataset timeline |
| State engine | every state, effective-status rule, conflict surfacing, fixed state vocabulary |
| Dependency engine | kind resolution (`approval:*`, `vendor:*`), pending/completed/blocked, filters |
| Date-risk engine | ON_TRACK / AT_RISK / OVERDUE / COMPLETED / None, delay evidence |
| Generators | demo-state mapping, claims-with-evidence, no hallucination, uncertainty fallback, baseline |
| Next action | 11 lexicon categories, marker matching, owner/detail resolution, most-recent-wins, pre-resolution markers ignored, sparse evidence, no-action-when-unsupported |
| Grounding gate | grounded / partially grounded / sparse / conflicting / invented completion, date, approval, vendor, customer contact / missing evidence |
| Role security | valid + invalid roles, wrong role, missing role, header/body mismatch, protected endpoints |
| Human evaluation | packet contents, submission validation, CSV round-trip, Cohen's and Fleiss' kappa arithmetic |
| Evaluation | metrics structure, prototype beats baseline, per-case content |
| API | health, list/detail, events/timeline/progress, lifecycle with role gates, audit, stub, dashboard, grounding-check, human-validation endpoints |

## 3. Evaluation methodology (synthetic)

The evaluation is a **baseline-vs-prototype experiment** over 64 curated cases
(`data/evaluation/evaluation_cases.csv`). Cases include 7 DEMO scenarios + the
7 failure-case categories and 34 regular tickets.

Reviewer rules are **deterministic and documented** in
`services/evaluation_service.py`:

```
prototype_understanding = 1 + state_match + blocker_match + next_action_match + date_match   # 0..5
prototype_followup      = prototype_understanding < 4
baseline_understanding  = 1 + baseline_state_match + baseline_date_completed_match            # 0..3
baseline_followup       = baseline_understanding < 3
```

- `state_match` — generated progress state equals the expected label.
- `blocker_match` — the expected blocker/waiter name appears in the explanation.
- `next_action_match` — the predicted next-action **category** equals the
  structurally derived expected category (falling back to the text check for
  cases that cannot be decided structurally). See `docs/NEXT_ACTION.md`.
- `date_match` — generated date status equals the expected status.

The reviewer never uses the generator's own labels — it reads the **rendered
customer text** (plus states for exactness), mirroring a human reading the output.

## 4. Metrics (latest run, 64 cases)

Scored by the same deterministic reviewer, but next action is now scored on its
**category** rather than on string identity (see `docs/NEXT_ACTION.md`).

| Metric | Baseline | Prototype |
|--------|----------|-----------|
| Mean understanding (0–5) | 2.344 | 4.516 |
| Follow-up required rate | 57.8% | 3.1% |
| State accuracy | — | 100% |
| Blocker/waiter accuracy | — | 100% |
| Next-action accuracy (category) | — | 94.6% |
| Next-action category accuracy (n=24) | — | 100% |
| Promised-date accuracy | — | 96.9% |
| Grounding ≥ 60 | — | 85.9% |

Run it anytime:
```bash
python -m scripts.measure_next_action   # read-only, no database writes
python -m scripts.run_evaluation        # full run, persists to the database
```

## 5. Grounding and refusal gate

`services/grounding_gate.py` validates *any* generator's output before it can
reach a customer. It is a validation layer around the existing generators, not a
replacement, and the optional LLM generator stays optional.

Checks performed:

1. Every claim cites at least one real event id, and every cited id exists on
   that ticket.
2. The rendered text does not assert a completion, a date, an approval, a vendor
   response or a customer contact that the evidence does not support.
3. When the system reports insufficient evidence, the text must be a refusal and
   no concrete next action may be stated.

The gate returns a structured report; `assert_grounded()` raises so tests and CI
can fail the build. It is reachable from the API:

```bash
curl -X POST "http://127.0.0.1:8000/api/tickets/DEMO-001/grounding-check"
```

All seven demo tickets currently pass. The gate found one real defect during
development: a ticket with zero events was advertising a next action with no
evidence, which is now impossible by construction.

## 6. Human validation — framework ready, NOT completed

### Why the deterministic reviewer is not enough

The synthetic reviewer is a documented rule, not a person. It can confirm that
the output contains the expected facts, but it cannot show that a real customer
or support agent finds the message clear, complete or trustworthy. Stating
otherwise would overstate the evidence.

**No human validation has been carried out.** The `human_reviews` table is empty,
and the API reports `validation_completed: false`.

### What is provided

- `services/human_evaluation_service.py` — packet building, submission
  validation, CSV round-trip, and agreement statistics.
- `GET /api/evaluation/human/packet?limit=12` — a blank review sheet pairing the
  ground-truth expected action with the generated action. Judgement columns are
  intentionally blank.
- `POST /api/evaluation/human/review` — record one reviewer's judgement.
- `GET /api/evaluation/human/summary` — agreement statistics.
- `data/evaluation/human_review_template.csv` — the same sheet as a file.

### Recommended panel

- **3–5 reviewers** (support agents or students acting as reviewers).
- **12 cases**, excluding resolved tickets, balanced across waiting, blocked,
  delayed, transferred and reopened states.
- Each reviewer independently fills: `decision` (ACCEPT / REJECT / UNCLEAR),
  `action_agrees`, `understanding` (1–5), `followup_required`, optional
  `comment`.

### Metrics computed

| Metric | Meaning |
|--------|---------|
| Acceptance rate | share of reviews marked ACCEPT |
| Next-action agreement | share where the stated action matches the expected action |
| Mean understanding | average 1–5 clarity score |
| Follow-up rate | share of reviewers who would still chase the ticket |
| Inter-reviewer agreement | **Cohen's kappa** for exactly 2 reviewers, **Fleiss' kappa** for 3 or more |

Both statistics are implemented in plain Python so the project keeps its
no-extra-dependencies property. When expected agreement is exactly 1.0 the
statistic is undefined; the framework reports 1.0 for perfect observed agreement
and `null` otherwise, rather than a misleading figure.

### How to run a real panel later

```bash
# 1. produce the blank sheet
python -c "from backend.app.database import SessionLocal; \
from backend.app.services.human_evaluation_service import HumanEvaluationService as S; \
db=SessionLocal(); print(S(db).export_template(limit=12)); db.close()"

# 2. reviewers fill it in, one row per reviewer per case

# 3. load it and read the statistics
python -c "from backend.app.database import SessionLocal; \
from backend.app.services.human_evaluation_service import HumanEvaluationService as S; \
from pathlib import Path; db=SessionLocal(); s=S(db); \
print(s.import_csv(Path('data/evaluation/human_review_filled.csv'))); \
print(s.summary()); db.close()"
```

Until rows exist, the correct statement in any report is: **"the human-validation
framework is implemented and tested; no human reviewers have been run."**