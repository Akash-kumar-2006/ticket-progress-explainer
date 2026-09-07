"""API integration tests: explanation lifecycle, role gates, audit trail."""
import pytest


TICKET = "TCK-1001"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["rules_version"] == "1.0.0"
    assert body["reference_date"] == "2026-09-07"


def test_tickets_list_and_detail(client):
    r = client.get("/api/tickets", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 119
    assert len(body["items"]) == 5

    d = client.get(f"/api/tickets/{TICKET}")
    assert d.status_code == 200
    assert d.json()["ticket_id"] == TICKET


def test_ticket_events_and_timeline_and_progress(client):
    ev = client.get(f"/api/tickets/{TICKET}/events")
    assert ev.status_code == 200 and ev.json()

    tl = client.get(f"/api/tickets/{TICKET}/timeline")
    assert tl.status_code == 200 and tl.json()["entries"]

    pg = client.get(f"/api/tickets/{TICKET}/progress")
    assert pg.status_code == 200
    assert pg.json()["progress_state"] in {"WAITING_FOR_VENDOR", "BLOCKED"}


def test_generate_explanation_and_versions(client):
    r = client.post(
        f"/api/tickets/{TICKET}/generate-explanation",
        headers={"X-Role": "SYSTEM", "X-Actor": "system"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ticket_id"] == TICKET
    assert body["explanation"]
    assert body["grounding_breakdown"], "must explain its own grounding"
    assert body["explanation_id"]

    ver = client.get(f"/api/tickets/{TICKET}/explanation/versions")
    assert ver.status_code == 200
    assert ver.json()["versions"]


def test_guard_against_unsupported_claims_on_generate(client):
    r = client.post(
        f"/api/tickets/{TICKET}/generate-explanation",
        headers={"X-Role": "SYSTEM", "X-Actor": "system"},
    )
    claims = r.json()["claims"]
    assert all(c["supported"] for c in claims), "all output claims must be evidence-backed"


def test_dashboard_metrics(client):
    r = client.get("/api/dashboard/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["tickets"] == 119


def test_lifecycle_requires_reviewer_then_admin(fresh_db, client):
    # generate delivers a DRAFT
    g = client.post(
        f"/api/tickets/{TICKET}/generate-explanation",
        headers={"X-Role": "SYSTEM", "X-Actor": "system"},
    )
    assert g.json()["explanation_id"]

    # an AGENT must not be able to review
    r_deny = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "agent1", "role": "AGENT", "decision": "APPROVE", "reason": "oops"},
    )
    assert r_deny.status_code == 403

    # first APPROVE moves DRAFT -> PENDING_REVIEW
    r1 = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "reviewer1", "role": "REVIEWER", "decision": "APPROVE", "reason": "ok"},
    )
    assert r1.status_code == 200 and r1.json()["status"] == "PENDING_REVIEW"

    # second APPROVE moves PENDING_REVIEW -> APPROVED
    r2 = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "reviewer2", "role": "REVIEWER", "decision": "APPROVE", "reason": "ok"},
    )
    assert r2.status_code == 200 and r2.json()["status"] == "APPROVED"

    # non-reviewer cannot publish
    pub_deny = client.post(
        f"/api/tickets/{TICKET}/explanation/publish",
        json={"actor": "agent1", "role": "AGENT"},
    )
    assert pub_deny.status_code == 403

    pub = client.post(
        f"/api/tickets/{TICKET}/explanation/publish",
        json={"actor": "support", "role": "REVIEWER"},
    )
    assert pub.status_code == 200 and pub.json()["status"] == "PUBLISHED"

    # only ADMIN can rollback a published explanation
    rb_deny = client.post(
        f"/api/tickets/{TICKET}/explanation/rollback",
        json={"actor": "agent1", "role": "AGENT", "reason": "x"},
    )
    assert rb_deny.status_code == 403

    rb = client.post(
        f"/api/tickets/{TICKET}/explanation/rollback",
        json={"actor": "admin", "role": "ADMIN", "reason": "factual review", "target_version": 1},
    )
    assert rb.status_code == 200
    assert rb.json()["new_version"] > rb.json()["rolled_back_to_version"]


def test_audit_trail_has_lifecycle_events(fresh_db, client):
    client.post(
        f"/api/tickets/{TICKET}/generate-explanation",
        headers={"X-Role": "SYSTEM", "X-Actor": "system"},
    )
    client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "reviewer1", "role": "REVIEWER", "decision": "APPROVE", "reason": "check"},
    )
    trail = client.get(f"/api/tickets/{TICKET}/audit").json()["audit"]
    actions = {a["action"] for a in trail}
    assert {"EXPLANATION_GENERATED", "EXPLANATION_APPROVED"} <= actions


def test_integration_stub(client):
    r = client.get("/api/integrations/stub/ticket/TCK-1001")
    assert r.status_code == 200
    body = r.json()
    assert body["ticket_id"] == "TCK-1001"

    ev = client.get("/api/integrations/stub/events/TCK-1001")
    assert ev.status_code == 200
    data = ev.json()
    assert data["count"] > 0
    assert isinstance(data["events"], list)