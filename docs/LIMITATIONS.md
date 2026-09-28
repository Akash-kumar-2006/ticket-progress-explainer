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

## 4. "Next action" is still partly an inference

- The next-action sentence is derived from the action-marker lexicon over real
  event text (`engines/action_markers.py`). It is always evidence-backed, and
  each prediction reports its category and confidence
  (`specific` / `generic` / `sparse`).
- Where no marker phrase is present the sentence stays generic, and where
  evidence is too sparse the system states no action at all rather than
  inventing one.
- The category accuracy of 100% covers only the 24 of 37 next-action cases whose
  correct category can be established from event structure alone. The remaining
  13 are not scored, because deciding them requires reading the note. See
  `NEXT_ACTION.md` for why this metric changed and what it does and does not
  prove.

## 5. No LLM involvement

- The default generator is a deterministic, rule-based template engine. An
  optional LLM generator interface exists (`generators/llm.py`) but is neither
  enabled nor required; it falls back to the rule-based output when no provider
  is configured.
- Should an LLM be connected later, `services/grounding_gate.py` is the safety
  net: it verifies that every claim cites a real event, that no completion,
  date, approval, vendor response or customer contact is invented, and that the
  generator refuses when evidence is insufficient. It is already enforced by 18
  tests and reachable from the API, so the LLM path would not ship ungated.

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
- Authorization is nonetheless enforced server-side: roles are validated against
  a fixed vocabulary, the `X-Role` header must agree with the body role, and the
  request schemas have no default role, so omitting it fails rather than granting
  privilege. See `SECURITY.md` for the production recommendation (real identity
  provider + PostgreSQL).

## 9. Evaluation is synthetic

- The reviewer is a deterministic, documented rule (see VALIDATION.md), not a
  human panel.
- A human-validation framework is implemented and tested — review packet,
  submission endpoint, CSV round-trip, acceptance rate, next-action agreement
  and Cohen's/Fleiss' kappa — but **no human reviewers have been run**, so no
  human agreement figure can be quoted. The API reports
  `validation_completed: false` until real rows exist.