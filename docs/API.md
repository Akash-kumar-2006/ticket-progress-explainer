# API reference

Base URL: `http://127.0.0.1:8000/api` · Interactive docs: `http://127.0.0.1:8000/docs`

All responses are JSON. Sensitive actions require role/actor (headers or body,
see each endpoint).

## Health & metadata

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service, versions, reference date, integration mode |

## Tickets

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tickets?limit=&search=&state=` | List tickets (paginated, filterable) |
| GET | `/tickets/{id}` | Ticket detail |
| GET | `/tickets/{id}/events` | Raw events for the ticket |
| GET | `/tickets/{id}/timeline` | Sorted timeline + duplicates/out-of-order/conflicts |
| GET | `/tickets/{id}/progress` | Progress state result (state, date status, reasons, blockers) |
| GET | `/tickets/{id}/dependencies` | Dependency chain |
| POST | `/tickets/import` | Import tickets/events (body: `{tickets, events}`) |
| POST | `/events` | Insert a single normalized event |

## Explanations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/tickets/{id}/generate-explanation` | Generate (DRAFT), header `X-Role`/`X-Actor` |
| GET | `/tickets/{id}/explanation` | Latest persisted explanation with evidence |
| GET | `/tickets/{id}/explanation/versions` | Version history |
| POST | `/tickets/{id}/explanation/review` | body `{actor, role, decision: APPROVE\|REJECT, reason}` |
| POST | `/tickets/{id}/explanation/publish` | body `{actor, role}` — requires APPROVED |
| POST | `/tickets/{id}/explanation/rollback` | body `{actor, role, reason, target_version?}` — ADMIN only |
| GET | `/tickets/{id}/audit` | Audit trail for the ticket |

## Dashboard & evaluation

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/metrics` | Totals by state/status/region/priority, grounding |
| GET | `/evaluation/summary` | Latest experiment metrics |
| GET | `/evaluation/results` | Per-case result rows |
| POST | `/evaluation/run` | Run the synthetic evaluation |
| POST | `/evaluation/human` | Store a human reviewer row for a case |

## Integration stub

| Method | Path | Description |
|--------|------|-------------|
| GET | `/integrations/stub` | Stub capabilities / contract |
| GET | `/integrations/stub/ticket/{id}` | Stub ticket fetch |
| GET | `/integrations/stub/events/{id}` | Stub events fetch |

## Role gates (500-level transparency)

| Action | Required role |
|--------|---------------|
| generate | SYSTEM or any (creates DRAFT) |
| review | REVIEWER, ADMIN |
| publish | REVIEWER, ADMIN (only from APPROVED) |
| rollback | ADMIN (only on PUBLISHED) |

## Example — generate an explanation

```bash
curl -X POST http://127.0.0.1:8000/api/tickets/TCK-1001/generate-explanation \
  -H "X-Role: SYSTEM" -H "X-Actor: system"
```

Response (abridged):

```json
{
  "ticket_id": "TCK-1001",
  "progress_state": "WAITING_FOR_VENDOR",
  "date_status": "ON_TRACK",
  "grounding_score": 91,
  "grounding_breakdown": ["Evidence coverage: ...", "Final Grounding Score: 91/100"],
  "explanation": "Your request is currently waiting for the vendor to provide the required item.\n\n...",
  "claims": [{ "category": "status", "text": "...", "evidence": ["EV-00006"], "supported": true }],
  "evidence": [{ "event_id": "EV-00006", "reason": "Latest vendor update", ... }]
}
```

## Example — review → publish → rollback

```bash
curl -X POST .../api/tickets/TCK-1001/explanation/review \
  -H "Content-Type: application/json" \
  -d '{"actor":"reviewer1","role":"REVIEWER","decision":"APPROVE","reason":"ok"}'
# → {"explanation_id":1,"status":"PENDING_REVIEW"}   (2nd approve → APPROVED)

curl -X POST .../api/tickets/TCK-1001/explanation/publish \
  -H "Content-Type: application/json" -d '{"actor":"support","role":"REVIEWER"}'
# → {..., "status":"PUBLISHED"}

curl -X POST .../api/tickets/TCK-1001/explanation/rollback \
  -H "Content-Type: application/json" \
  -d '{"actor":"admin","role":"ADMIN","reason":"factual review","target_version":1}'
# → {"rolled_back_to_version":1,"new_version":2}
```