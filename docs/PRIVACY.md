# Privacy & data handling

## 1. Design posture

This system explains **customer-facing progress**. Its privacy posture is
"exactly what the explanation needs, nothing more":

- The generated text is derived from **events already available to the support
  team** that describe the ticket's workflow (status, team, approvals, vendors,
  promised dates).
- Work notes are **snipped** to a short preview inside an update sentence; the
  raw note text is never echoed wholesale.
- Events are only surfaced through the **evidence selection** step, and only the
  selected IDs are attached to generated claims.

## 2. Data minimization

| Element | In generated output? | Reason |
|---------|----------------------|--------|
| Ticket ID / subject | Yes (header fields) | needed to identify the request |
| Customer name / contact | No | not used by any engine |
| Free-form work-note body | Partial (≤120 char snippet) | brief update only |
| Internal dependency text | Yes, but rephrased | customer must know what it is waiting on |
| Vendor name | Yes | explains the wait |
| Agent names | No | work is attributed by team, not individual |
| Approver names | No | team-level attribution only |

## 3. Offline stub & integrations

- The ticketing integration is an **offline stub** (`integrations/ticketing_stub.py`);
  no network call, no credentials, no external data leaves the machine.
- `fetch_*` functions carry documented return contracts so a real ticketing
  backend can be swapped in. When connecting a real system, re-run the privacy
  review: the *contracts* stay the same, but the *data source* changes.

## 4. Access control & accountability

- The API enforces the **least privilege** for lifecycle actions
  (review → REVIEWER/ADMIN, publish → REVIEWER/ADMIN, rollback → ADMIN).
- Every lifecycle mutation writes an immutable **audit row**
  (`audit_logs`): actor, role, action, old/new value, reason, source, timestamp.
- Version history keeps every previously published explanation retrievable
  (forensic recall after rollback).

## 5. Retention & disposal

- A single SQLite file holds the demo data. Delete it to reset:
  `Remove-Item ticket_progress.db` / `rm ticket_progress.db`.
- `.gitignore` excludes the database file, `__pycache__`, `node_modules`,
  `.pytest_cache` and build artifacts so no customer-like data is committed.
- Synthetic dataset uses placeholder data (e.g. `CUST-TCK-1001`); no real
  personal data exists anywhere in the repository.

## 6. Threat notes

- Explanation content is generated from local events — a user cannot inject
  content into the explanation itself; event messages are masked to short
  snippets.
- Role gates live in the API layer; in production they must be backed by the
  ticketing system's identity provider (documented in CHANGE_CONTROL.md).