# Known limitations

This section deliberately documents what the project **does not** do, so that
an evaluator sees an honest engineering boundary rather than an overclaim.

## 1. Synthetic data

- All scenarios run on reproducible synthetic data (seed 42). The numbers
  ("waiting on approval", "vendor delays") are simulated to resemble real
  regional-follow-up workflows but are **not** production data.
- Real-world noise (unicode quotes, half-written vendor events, deleted events,
  partially reconciled statuses) was modeled only to the degree visible in the
  seed set. A real feed may expose more.

## 2. Snapshot-based dates

- Date risk is computed relative to a fixed **reference date** (`REFERENCE_DATE`,
  default `2026-09-07` via `settings.reference_date_obj`). Evaluations are
  reproducible because time does not move; in production the reference would be
  "now" at request time.

## 3. Baseline is intentionally minimal

- The baseline control is *status-only* ("Your request is currently IN_PROGRESS") +
  a completed-date flag. That makes the prototype-vs-baseline gap a fair,
  conservative comparison, but the baseline does not attempt to be a strong
  competitor.

## 4. "Next action" is an inference

- The next-expected-action sentence is derived by the state engine from the
  most relevant event. It is always evidence-backed, but its *content* is a
  prediction (e.g. "the vendor is expected to provide: X"). When dependencies
  are vague, the action sentence stays generic. Measured next-action accuracy
  is ~49% on the synthetic set.

## 5. No LLM involvement

- The default generator is a deterministic, rule-based template engine. An
  optional LLM generator interface exists (`generators/llm.py`) but is neither
  enabled nor required; any LLM use would trade explainability and determinism
  for fluency, and would need its own grounding/refusal tests before production.

## 6. Geographic / org granularity

- "Regional transfer" detection is limited to the built-in regions and teams in
  `constants.py`. A transfer is inferred only from `TEAM_TRANSFER` events or a
  change of team on `ASSIGNMENT_CHANGE`.

## 7. Storage

- SQLite is the default store — single-writer, laptop-grade. Horizontal scaling
  would require PostgreSQL (supported via `DATABASE_URL`, models are
  DB-agnostic).

## 8. Role model

- Roles are plain header/body strings. This is a demonstration dependency; the
  API contract is role names, not identity tokens.

## 9. Evaluation is synthetic

- The reviewer is a deterministic, documented rule (see VALIDATION.md), not a
  human panel. Human-validated rows can be stored via `POST /evaluation/human`
  and remain separate from the synthetic runs; they are not faked.