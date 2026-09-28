# Next-action prediction

## The previous limitation

Next-action prediction was the weakest metric in the evaluation
(**48.6%**). Two distinct problems were behind it.

### 1. There was no action lexicon

`ProgressStateEngine` returned one of roughly thirteen hard-coded sentences
chosen by progress state. The wording of the actual work notes was ignored
except for a single `"schedul"` substring test. A note saying *"vendor has
shipped, we will verify the fix on Monday"* produced the same generic
"Work is continuing on the ticket." as a note with no content at all.

### 2. The metric could not measure prediction quality

`next_action_match` compared the generated explanation against
`expected_next_action`, a value produced by **the same engine that generated the
output**. That is a self-comparison, not a measurement. Two defects made it
worse:

- 15 of the 64 cases carried a literal `"nan"` in the expected sentence, caused
  by a NaN leak in the case builder (`str(row.get("message") or "")` returns
  `"nan"` for an empty cell, because NaN is truthy). Those cases could never match.
- The case builder did not populate `dependency_title`, so approvals were titled
  `Task approval:Security` in the reference data but `Security approval` in the
  live system.

Together these accounted for **all 19 of the 19 misses**. Prediction quality was
never actually the cause of the low score.

## What changed

### A. Action-marker lexicon

`backend/app/engines/action_markers.py` holds a structured lexicon: each
category has a key, a label, a list of lowercase marker phrases, and a
sentence template.

| Category | Example markers |
|----------|-----------------|
| `APPROVAL` | pending approval, approval required, manager approval, security review, awaiting sign-off |
| `VENDOR_RESPONSE` | awaiting vendor, vendor response, vendor follow-up, replacement part, awaiting shipment |
| `CUSTOMER_RESPONSE` | waiting on customer, awaiting customer, customer confirmation, customer to provide |
| `ESCALATION` | escalat, senior review, management review |
| `REASSIGNMENT` | reassign, hand off, handing off, handover, transfer to, routing to |
| `VERIFICATION` | verify, validation, retest, confirm the fix, test the |
| `DEPLOYMENT` | deploy, patch, rollout, maintenance window, configuration update |
| `INFORMATION` | provide logs, collect evidence, diagnostic data, reproduce issue |
| `INVESTIGATION` | investigat, troubleshoot, root cause, reproduc |
| `FOLLOW_UP` | follow up with the customer, update requester |
| `CLOSURE` | close the ticket, confirm resolution |

Ordering is explicit and matters. `VERIFICATION` is evaluated **before**
`DEPLOYMENT` so that "verify the fix once deployed" is classified as
verification rather than as a deployment.

Selection rules:

- Only events with real text are considered, and only after the last
  resolution or reopen (an old "awaiting vendor" note must not drive the next
  action of a ticket that has since been resolved).
- The **most recent** matching event wins.
- Every signal carries the `event_id` that produced it, so the claim is
  traceable exactly like the status and blocker claims.
- The evidence selector now guarantees that any event cited by a next-action
  claim is visible in the evidence panel, even when a newer event of the same
  type won the per-category slot.

### B. Sparse-evidence handling

- **No marker anywhere** → the existing state-specific sentence is kept, tagged
  `confidence="generic"`.
- **One event with text, no marker** → a safe `STATUS_CONFIRMATION` action
  ("The support team is confirming the current status…"), tagged
  `confidence="sparse"`. It names no specific work.
- **No events at all** → **no next action is stated at all.** `ProgressResult`
  drops the sentence, records the reason "No next action stated: no ticket event
  supports one", and the explanation falls back to the existing
  insufficient-evidence wording.

This last rule was found by the grounding gate, not by hand: DEMO-006 has zero
events yet was advertising "The assigned team is starting the investigation".

### C. Explainability

Two new fields are exposed on every explanation and in the ticket detail API:

- `next_action_category` — the lexicon key, e.g. `VENDOR_RESPONSE`
- `next_action_confidence` — `specific` | `generic` | `sparse`

## Evaluation methodology change

`next_action_match` is now scored on the **category**, and the expected category
is derived **structurally** in the case builder from event types and dependency
kinds:

```
RESOLVED                      -> CLOSURE
REOPENED                      -> INVESTIGATION
pending approval dependency   -> APPROVAL
pending vendor dependency     -> VENDOR_RESPONSE
pending customer dependency   -> CUSTOMER_RESPONSE
BLOCKED / internal pending    -> DEPENDENCY_PENDING
TRANSFERRED                   -> REASSIGNMENT
last structural event type    -> its mapped category
otherwise                     -> UNSPECIFIED (not scored)
```

This label does **not** read marker phrases, so it is independent of the lexicon
the system under test uses. Cases whose action cannot be decided structurally
are labelled `UNSPECIFIED` and excluded from the category score rather than
being guessed. The old free-text comparison is retained and reported as
`next_action_text_match_rate`, but it is no longer the headline number.

## Measured results

Same dataset, same 64 cases, same 37 next-action cases.

| Metric | Before | After |
|--------|--------|-------|
| `next_action_accuracy` | 0.486 | **0.946** |
| `next_action_category_accuracy` (n=24, new) | – | **1.000** |
| `next_action_text_match_rate` | 0.486 | 0.946 |
| `blocker_accuracy` | 0.792 | 1.000 |
| `state_accuracy` | 1.000 | 1.000 |
| `promised_date_accuracy` | 0.969 | 0.969 |
| `grounding_accuracy` | 0.859 | 0.859 |
| mean understanding | 4.359 | 4.516 |
| follow-up rate | 26.6% | 3.1% |
| tests | 47 | 155 |

Regressions: **none**. No metric decreased.

### Honest reading of these numbers

The jump from 48.6% to 94.6% is **not** a claim that the predictor became twice
as clever. It is mostly the correction of two label defects that made the old
metric unpassable, plus a genuine capability addition (the lexicon).

The number that best reflects the new capability is
`next_action_category_accuracy = 1.000` over the 24 structurally decidable
cases: for every case where the correct action category can be established
without reading marker text, the system picks the right category.

Two honest caveats:

1. Blocker and next-action reference labels are still derived from the engine
   itself. They are useful as regression signals, not as independent evidence of
   correctness. The category score is the one independent comparison available
   offline.
2. 13 of 37 cases are `UNSPECIFIED` and unscored, because their correct action
   genuinely cannot be determined from event structure alone — deciding whether
   a work note means "investigate" or "deploy" requires reading it. A human
   panel (see `docs/VALIDATION.md`) is the only honest way to score those.

## Reproducing

```bash
python -m scripts.generate_evaluation_cases   # rebuild reference labels
python -m scripts.measure_next_action         # read-only, no DB writes
python -m scripts.run_evaluation              # full run, persists results
```

`scripts/measure_next_action.py` reuses the production scorer, so it cannot drift
from the real evaluation.
