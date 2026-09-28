"""Role-gate and authorization tests.

Covers the review requirements: authorized access, unauthorized access, wrong
role, missing authentication, protected-endpoint access, invalid role rejection,
and agreement between the X-Role header and the body role.

These tests describe DEMO-GRADE security. SQLite and a caller-asserted role are
acceptable for an offline demonstration; production needs a real identity
provider and PostgreSQL. See docs/SECURITY.md.
"""
from __future__ import annotations

import pytest

from backend.app.api.routes import KNOWN_ROLES
from backend.app.api.routes import enforce_role

TICKET = "TCK-1002"
GEN_HEADERS = {"X-Role": "SYSTEM", "X-Actor": "system"}


@pytest.fixture
def draft(client):
    """A ticket with a DRAFT explanation ready for review/publish."""
    r = client.post(
        f"/api/tickets/{TICKET}/generate-explanation",
        headers=GEN_HEADERS,
        json={"generator": "rule_based", "persist": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ----------------------------------------------------------------------
# Role vocabulary
# ----------------------------------------------------------------------
def test_role_vocabulary_is_ticket_support_only():
    assert "ADMIN" in KNOWN_ROLES
    assert "REVIEWER" in KNOWN_ROLES
    assert "SUPPORT_AGENT" in KNOWN_ROLES
    assert "CUSTOMER" in KNOWN_ROLES
    # No roles from unrelated templates.
    for unrelated in ("DOCTOR", "PATIENT", "NURSE", "DOCTEUR"):
        assert unrelated not in KNOWN_ROLES


def test_enforce_role_rejects_unknown_role():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        enforce_role("WIZARD", ("ADMIN",), None)
    assert exc.value.status_code == 400


def test_enforce_role_rejects_empty_role():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        enforce_role("", ("ADMIN",), None)
    assert exc.value.status_code == 400


def test_enforce_role_allows_valid_role():
    from fastapi import HTTPException

    assert enforce_role("admin", ("ADMIN",), None) == "ADMIN"
    with pytest.raises(HTTPException) as exc:
        enforce_role("REVIEWER", ("ADMIN",), None)
    assert exc.value.status_code == 403


# ----------------------------------------------------------------------
# Authorized access still works
# ----------------------------------------------------------------------
def test_reviewer_can_review(client, draft):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "rev1", "role": "REVIEWER", "decision": "APPROVE"},
    )
    assert r.status_code == 200


def test_admin_can_review(client, draft):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "admin1", "role": "ADMIN", "decision": "APPROVE"},
    )
    assert r.status_code == 200


def test_admin_can_rollback_published_explanation(client, draft):
    client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "rev1", "role": "REVIEWER", "decision": "APPROVE"},
    )
    client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "rev2", "role": "REVIEWER", "decision": "APPROVE"},
    )
    client.post(f"/api/tickets/{TICKET}/explanation/publish", json={"actor": "rev1", "role": "REVIEWER"})
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/rollback",
        json={"actor": "admin1", "role": "ADMIN", "reason": "correction", "target_version": 1},
    )
    assert r.status_code == 200


# ----------------------------------------------------------------------
# Unauthorized / wrong role
# ----------------------------------------------------------------------
@pytest.mark.parametrize("role", ["AGENT", "SUPPORT_AGENT", "CUSTOMER", "SYSTEM"])
def test_non_reviewer_cannot_review(client, draft, role):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "someone", "role": role, "decision": "APPROVE"},
    )
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("role", ["AGENT", "SUPPORT_AGENT", "CUSTOMER"])
def test_non_reviewer_cannot_publish(client, draft, role):
    r = client.post(f"/api/tickets/{TICKET}/explanation/publish", json={"actor": "x", "role": role})
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("role", ["AGENT", "SUPPORT_AGENT", "CUSTOMER", "REVIEWER", "SYSTEM"])
def test_non_admin_cannot_rollback(client, draft, role):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/rollback",
        json={"actor": "x", "role": role, "reason": "r"},
    )
    assert r.status_code == 403, r.text


# ----------------------------------------------------------------------
# Missing authentication
# ----------------------------------------------------------------------
def test_missing_role_is_treated_as_unauthorized(client, draft):
    """A body without a role cannot pass a privileged gate.

    The request schemas have no default role, so omitting it is a validation
    error (422) rather than a silent grant of privilege.
    """
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "anon", "decision": "APPROVE"},
    )
    assert r.status_code in (400, 422), r.text


def test_missing_actor_is_still_gated_by_role(client, draft):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/rollback",
        json={"role": "ADMIN", "reason": "no actor supplied"},
    )
    # ADMIN role is valid, so the request passes the role gate on its own.
    assert r.status_code in (200, 400, 404)


# ----------------------------------------------------------------------
# Invalid / mismatched role input
# ----------------------------------------------------------------------
def test_invalid_role_is_rejected_by_api(client, draft):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        json={"actor": "x", "role": "SUPERADMIN", "decision": "APPROVE"},
    )
    assert r.status_code == 400, r.text


def test_header_and_body_role_must_agree(client, draft):
    """X-Role is the identity stand-in: a body cannot claim more than the header."""
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        headers={"X-Role": "SUPPORT_AGENT", "X-Actor": "agent1"},
        json={"actor": "agent1", "role": "ADMIN", "decision": "APPROVE"},
    )
    assert r.status_code == 403, r.text


def test_matching_header_and_body_role_is_allowed(client, draft):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        headers={"X-Role": "REVIEWER", "X-Actor": "rev1"},
        json={"actor": "rev1", "role": "REVIEWER", "decision": "APPROVE"},
    )
    assert r.status_code == 200, r.text


def test_invalid_header_role_is_rejected(client, draft):
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/review",
        headers={"X-Role": "ROOT", "X-Actor": "x"},
        json={"actor": "x", "role": "ROOT", "decision": "APPROVE"},
    )
    assert r.status_code == 400, r.text


# ----------------------------------------------------------------------
# Protected endpoints
# ----------------------------------------------------------------------
def test_protected_endpoints_reject_unknown_ticket(client):
    for path, payload_body in (
        ("/explanation/review", {"role": "ADMIN", "decision": "APPROVE"}),
        ("/explanation/publish", {"role": "ADMIN"}),
        ("/explanation/rollback", {"role": "ADMIN", "reason": "r"}),
    ):
        r = client.post(f"/api/tickets/NO-SUCH-TICKET{path}", json=payload_body)
        assert r.status_code == 404, f"{path} should 404 for a missing ticket"


def test_role_is_not_enforced_by_the_client_alone(client, draft):
    """A privileged call made without any credential header is still rejected
    when the body role is not permitted."""
    r = client.post(
        f"/api/tickets/{TICKET}/explanation/publish",
        json={"actor": "support_agent", "role": "SUPPORT_AGENT"},
    )
    assert r.status_code == 403, r.text


def test_generation_endpoint_remains_open_to_system_role(client):
    r = client.post(
        f"/api/tickets/{TICKET}/generate-explanation",
        headers=GEN_HEADERS,
        json={"generator": "rule_based", "persist": False},
    )
    assert r.status_code == 200, r.text
