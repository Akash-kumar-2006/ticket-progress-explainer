# Change control

This document describes how generated explanations change over time, who is
allowed to change them, and how those changes remain auditable.

## 1. Versioning model

Every ticket has its own explanation **version sequence**. A new version is
created when:

- the explanation generator runs (DRAFT),
- a rollback restores older content (new version, `source_version` set).

```text
v1 DRAFT → PENDING_REVIEW → APPROVED → PUBLISHED
                                            ↘ (bad content?)
v2 = rollback of v1 → PUBLISHED        (source_version=1)
```

The latest version per ticket is served by
`GET /api/tickets/{id}/explanation/versions`.

## 2. Lifecycle states

| State | Meaning | Who can move it |
|-------|---------|-----------------|
| DRAFT | Generated, not reviewed | generator (SYSTEM) |
| PENDING_REVIEW | First approval recorded | REVIEWER / ADMIN |
| APPROVED | Second approval recorded | REVIEWER / ADMIN |
| PUBLISHED | Sent to the customer channel | REVIEWER / ADMIN only from APPROVED |
| REJECTED | Reviewer rejected | REVIEWER / ADMIN |

Status transitions enforced in `api/routes.py`; publishing is only allowed from
APPROVED; rollback is only allowed on PUBLISHED content.

## 3. Role matrix

| Action | CUSTOMER | SUPPORT_AGENT | REVIEWER | ADMIN |
|--------|----------|---------------|----------|-------|
| View reports | ✅ | ✅ | ✅ | ✅ |
| Generate (DRAFT) | ❌ (SYSTEM trigger) | ✅ via API | ✅ | ✅ |
| Approve / reject | ❌ | ❌ | ✅ | ✅ |
| Publish | ❌ | ❌ | ✅ | ✅ |
| Rollback | ❌ | ❌ | ❌ | ✅ |

In this codebase roles are simple strings (headers/body). In a production
deployment these must come from the organization's IdP; the API contract is
role-names, not authentication tokens.

## 4. Audit trail

Every state change writes an `audit_logs` row:

| Field | Example |
|-------|---------|
| action | `EXPLANATION_PUBLISHED` |
| actor | `support` |
| role | `REVIEWER` |
| old_value | `APPROVED` |
| new_value | `PUBLISHED` |
| reason | `high-impact action: customer-facing publication requires approval` |
| source | `api` |

Verified by tests: `EXPLANATION_GENERATED`, `EXPLANATION_APPROVED`,
`EXPLANATION_PUBLISHED`, `ROLLBACK_EXECUTED`.

## 5. Rule and model versions

- `RULES_VERSION` and `MODEL_VERSION` (defaults `1.0.0`) are stamped on every
  generated explanation so an old explanation can be traced to the rule set that
  produced it.
- Rule changes flow through normal code review + tests; they do not rewrite
  published explanations retroactively (immutable history).

## 6. Recommended release checklist

1. Change engines / generators in a branch.
2. Add or update pytest cases (state, dependency, date risk, anti-hallucination,
   role gates).
3. Re-run `python -m pytest` and the evaluation experiment
   (`scripts/run_evaluation.py`) to confirm no meaningful regression.
4. Bump `MODEL_VERSION` / `RULES_VERSION`; document the change in this log.
5. Deploy; old explanations remain readable in version history.