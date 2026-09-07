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

`python -m pytest` → **47 tests**:

| Area | Coverage |
|------|----------|
| Timeline engine | chronological order, duplicate/out-of-order/conflict flags, dataset timeline |
| State engine | every state, effective-status rule, conflict surfacing, fixed state vocabulary |
| Dependency engine | kind resolution (`approval:*`, `vendor:*`), pending/completed/blocked, filters |
| Date-risk engine | ON_TRACK / AT_RISK / OVERDUE / COMPLETED / None, delay evidence |
| Generators | demo-state mapping, claims-with-evidence, no hallucination, uncertainty fallback, baseline |
| Evaluation | metrics structure, prototype beats baseline, per-case content |
| API | health, list/detail, events/timeline/progress, lifecycle with role gates, audit, stub |

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
- `next_action_match` — the expected next-action text appears.
- `date_match` — generated date status equals the expected status.

The reviewer never uses the generator's own labels — it reads the **rendered
customer text** (plus states for exactness), mirroring a human reading the output.

## 4. Metrics (latest run, 64 cases)

| Metric | Baseline | Prototype | Improvement |
|--------|----------|-----------|-------------|
| Mean understanding (0–5) | 2.344 | 4.359 | **+86%** |
| Follow-up required rate | 57.8% | 26.6% | **−54.1%** |
| State accuracy | — | 76.6% | — |
| Blocker/waiter accuracy | — | 79.2% | — |
| Next-action accuracy | — | 48.6% | — |
| Promised-date accuracy | — | 96.9% | — |
| Grounding ≥ 60 | — | 85.9% | — |

Run it anytime:
```bash
python -m scripts.run_evaluation
```

## 5. Human validation (separate from synthetic)

- Rows are exposed for human labels via `POST /api/evaluation/human`
  (`case_id`, `human_understanding_score`, `human_followup_required`).
- Human rows are stored against the same `evaluation_results` table but are
  clearly distinct from synthetic runs; the synthetic reviewer is never
  presented as human judgment.
- Collecting a human panel is out of scope for the offline demo and is not
  simulated or faked.