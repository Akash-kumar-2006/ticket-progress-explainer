# Security and role enforcement

## Current state (demo-grade)

This project is an offline academic demonstration. It runs on SQLite and uses a
**caller-asserted role** as its identity mechanism. That is deliberate and
sufficient for evaluating the explanation engine, but it is **not** production
authentication.

### How identity works

Requests may state a role in two places:

- the `X-Role` request header (the identity stand-in), and
- the `role` field in the request body.

`enforce_role()` in `backend/app/api/routes.py` validates every privileged call:

1. The role must appear in the known ticket-support vocabulary
   (`CUSTOMER`, `SUPPORT_AGENT`, `AGENT`, `REVIEWER`, `ADMIN`, `SYSTEM`).
   Anything else is rejected with **400**.
2. If an `X-Role` header is present it must **agree** with the body role,
   otherwise **403**. A body cannot claim more privilege than the header.
3. The role must be in the list allowed for that action, otherwise **403**.
4. The request schemas (`ReviewRequest`, `PublishRequest`, `RollbackRequest`)
   have **no default role**. Omitting it is a validation error (**422**) rather
   than a silent grant of privilege.

### Who may do what

| Action | Allowed roles |
|--------|---------------|
| Generate an explanation | `SYSTEM` (plus the public read endpoints) |
| Review an explanation | `REVIEWER`, `ADMIN` |
| Publish an explanation | `REVIEWER`, `ADMIN` |
| Roll back a published explanation | `ADMIN` |
| Read tickets, timeline, dependencies | any caller |

### What is enforced server-side

- Authorization is checked in the route handlers, not in the UI. Hiding a button
  in the React dashboard is **not** treated as a security control.
- All privileged actions are written to the audit trail with actor, role, old
  value and new value.
- Ticket-support roles only. No roles from unrelated domains exist in the
  codebase, and the test suite asserts this.

## Known limitations

| Limitation | Why it exists |
|------------|---------------|
| The caller states its own role | There is no identity provider in an offline demo |
| No passwords, tokens or sessions | Same reason |
| `SYSTEM` can generate any explanation | Generation is not customer-visible; publication is gated |
| SQLite, single file | Local development only; no concurrent-write story |

## Production recommendation

Before any real deployment:

1. **Real identity provider** — OIDC/SAML (Entra ID, Okta, Auth0). Replace the
   `X-Role` header with a verified token and read roles from signed claims.
2. **Server-side authorization from those claims** — keep `enforce_role`, but
   source the role from the token, never from the request body.
3. **PostgreSQL** — replace SQLite for concurrency, backups and audit retention.
   The SQLAlchemy models are already database-agnostic; only `DATABASE_URL`
   changes.
4. **Append-only audit storage** — ship the audit trail to write-once storage.
5. **Rate limiting and per-actor quotas** on generation endpoints.

The engines, evaluation harness and grounding gate are unaffected by any of this
and require no changes.
