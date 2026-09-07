# Error analysis & edge cases

## 1. Where the dataset gets "bad" on purpose

The synthetic dataset (seed 42) ships with **deliberate, documented edge cases**
so the pipeline's *tolerance* and *honesty* can be evaluated. Validation
(`scripts/validate_dataset.py`) reports exactly what is expected:

| Issue | Event(s) | Level | Treatment |
|-------|----------|-------|-----------|
| Duplicate event ID | `EV-01020` | error | skipped at import; documented in seed output (`duplicate_events_skipped=1`) |
| RESOLVED → IN_PROGRESS (impossible) | `EV-00361`, `EV-00827`, `EV-01007` | error | kept, **flagged**, reduces grounding, surfaces in conflicts |
| Out-of-order timestamp | `EV-01017` | warning | kept, flagged in the timeline |

`data/processed/validation_report.json` reproduces this every run.

## 2. Failure-case taxonomy (as used by evaluation cases)

`scripts/generate_evaluation_cases.py` classifies each evaluation case:

| failure_case | Example | Pipeline behaviour |
|--------------|---------|--------------------|
| `conflicting_events` | RESOLVED then IN_PROGRESS | effective status = latest valid event; conflict shown, grounding penalized (case DEMO-005, EV-01007) |
| `duplicate_events` | same event ID twice | duplicate skipped/surfaced in timeline `duplicates` |
| `out_of_order_events` | timestamp earlier than a previous event | flagged in timeline `out_of_order` |
| `overdue_promised_date` | promised date passed, unresolved | state DELAYED, date OVERDUE (case DEMO-004) |
| `missing_evidence` | assignment only, no activity | INVESTIGATING with insufficient-evidence safety net (case DEMO-006) |
| `multiple_regional_transfers` | two or more transfers | TRANSFERRED or follow-the-latest logic, transfer mentioned in explanation |
| `reopened` | RESOLUTION then REOPENED | REOPENED state (case DEMO-007) |

## 3. Anti-hallucination failure handling (the important one)

A naive generator would produce a confident sentence even when data is missing.
This system instead:

1. Requires a supporting evidence ID for **every emitted claim**
   (`RuleBasedExplanationGenerator.generate`, enforced by tests).
2. Drops any claim whose evidence cannot be attached.
3. If the **status claim itself** is unsupported → emits:
   > "Your ticket is currently in progress. The available updates do not
   > provide enough information to reliably explain the next step."
4. Marks `insufficient_evidence=true` and signals it in the UI.

Verified by tests `test_every_sentence_is_supported_by_evidence` and
`test_insufficient_evidence_yields_explicit_uncertainty_only`.

## 4. Unsupported-claim test coverage

| Guard | Test |
|-------|------|
| No claim without evidence in output | `test_every_sentence_is_supported_by_evidence` |
| Referenced events must exist | same test (ID set check) |
| Uncertainty only when insufficient | `test_insufficient_evidence_yields_explicit_uncertainty_only` |
| Never claim "resolved" when unresolved | `test_no_hallucinated_resolution` |
| Next action always evidence-backed | `test_next_action_has_evidence` |
| Conflicts surfaced, not hidden | `test_conflict_flag_surfaced_for_resolved_then_in_progress`, `test_known_factual_claims_present` (DEMO-005) |

## 5. Known weaknesses (measured honestly)

- **next_action accuracy ≈ 49%** in the synthetic evaluation: the "next
  expected action" is an *inference*; if underlying events are sparse or worded
  vaguely, the generated sentence is generic even when it is evidence-backed.
- State accuracy ≈ 77% across all cases (including hard/edge cases); for the
  curated DEMO cases the mapping is exact (see demo table).
- Follow-up sentences rephrase dependency titles; verbose English titles can
  produce slightly awkward phrasing.
- See docs/LIMITATIONS.md for the full, honest list.