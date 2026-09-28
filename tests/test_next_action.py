"""Next-action prediction tests.

Covers the scenarios named in the review feedback: approval pending, customer
response pending, vendor response pending, escalation, reassignment,
investigation, deployment, verification, closure, sparse evidence and
conflicting evidence.

The scenarios are built as in-memory events so each assertion is exact and does
not depend on the sampled synthetic dataset.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.app.engines.action_markers import (
    ACTION_CATEGORIES,
    CATEGORY_BY_KEY,
    find_category,
    infer_action,
)
from backend.app.engines.models import DependencyInfo, EventData

BASE = datetime(2026, 9, 1, 9, 0)
NOW = datetime(2026, 9, 7, 12, 0)


def ev(event_id: str, event_type: str, message: str, hours: int = 0, **extra) -> EventData:
    return EventData(
        event_id=event_id,
        ticket_id="T-1",
        timestamp=BASE + timedelta(hours=hours),
        event_type=event_type,
        message=message,
        **extra,
    )


def dep(dep_id: str, kind: str, owner: str = "NA Support", **extra) -> DependencyInfo:
    return DependencyInfo(
        dependency_id=dep_id,
        title=extra.pop("title", "Task"),
        kind=kind,
        status=extra.pop("status", "pending"),
        owner=owner,
        created_at=BASE,
        source_event_id=extra.pop("source_event_id", "E0"),
        **extra,
    )


# ----------------------------------------------------------------------
# 1. The lexicon itself
# ----------------------------------------------------------------------
def test_lexicon_covers_the_reviewed_action_families():
    keys = {c.key for c in ACTION_CATEGORIES}
    for required in (
        "APPROVAL",
        "VENDOR_RESPONSE",
        "CUSTOMER_RESPONSE",
        "ESCALATION",
        "REASSIGNMENT",
        "INVESTIGATION",
        "DEPLOYMENT",
        "VERIFICATION",
        "INFORMATION",
        "FOLLOW_UP",
        "CLOSURE",
    ):
        assert required in keys, f"lexicon is missing the {required} category"


def test_every_marker_is_lowercase_and_non_empty():
    for category in ACTION_CATEGORIES:
        assert category.markers, f"{category.key} has no markers"
        for marker in category.markers:
            assert marker == marker.lower()
            assert marker.strip()


# ----------------------------------------------------------------------
# 2. Marker matching per scenario
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "message,expected_key",
    [
        ("Security approval requested before rollout.", "APPROVAL"),
        ("This needs manager approval.", "APPROVAL"),
        ("Awaiting sign-off from the change board.", "APPROVAL"),
        ("Waiting on customer for the account number.", "CUSTOMER_RESPONSE"),
        ("Awaiting customer reply on the requested logs.", "CUSTOMER_RESPONSE"),
        ("Customer confirmation required before we continue.", "CUSTOMER_RESPONSE"),
        ("Awaiting vendor confirmation on the shipment.", "VENDOR_RESPONSE"),
        ("Vendor follow-up required on the open order.", "VENDOR_RESPONSE"),
        ("This needs to be escalated to the account manager.", "ESCALATION"),
        ("Request escalated for senior review.", "ESCALATION"),
        ("Ticket will be reassigned to the EMEA queue.", "REASSIGNMENT"),
        ("Handing off to the next regional team.", "REASSIGNMENT"),
        ("Starting the investigation of the failure.", "INVESTIGATION"),
        ("Engineer will troubleshoot the connection.", "INVESTIGATION"),
        ("Patch will be deployed in tonight's window.", "DEPLOYMENT"),
        ("Scheduling the deployment for the weekend.", "DEPLOYMENT"),
        ("We will verify the fix once deployed.", "VERIFICATION"),
        ("Please retest after the change.", "VERIFICATION"),
        ("Please provide logs from the affected host.", "INFORMATION"),
        ("Support will follow up with the customer tomorrow.", "FOLLOW_UP"),
        ("Once confirmed we will close the ticket.", "CLOSURE"),
    ],
)
def test_find_category_per_scenario(message, expected_key):
    assert find_category(message).key == expected_key


def test_find_category_ignores_irrelevant_text():
    assert find_category("Routine note with no action wording.") is None
    assert find_category("") is None


# ----------------------------------------------------------------------
# 3. Inference produces a grounded, evidence-linked action
# ----------------------------------------------------------------------
def test_approval_pending_action_is_grounded():
    events = [
        ev("E1", "STATUS_CHANGE", "Assigned to NA Support.", 0),
        ev("E2", "APPROVAL_REQUESTED", "Security approval requested before rollout.", 2,
           approval_type="Security", team="Security Review"),
    ]
    deps = [dep("approval:security", "approval", owner="Security Review",
                title="Security approval", source_event_id="E2")]
    signal = infer_action(events, deps, "WAITING_FOR_APPROVAL")
    assert signal.category == "APPROVAL"
    assert signal.evidence_ids == ["E2"]
    assert "Security Review" in signal.text
    assert "security" in signal.text.lower()


def test_vendor_response_pending_action_mentions_the_item():
    events = [
        ev("E1", "VENDOR_UPDATE", "Replacement part delayed by the supplier.", 1,
           vendor="Northwind Components", vendor_item="replacement part"),
    ]
    deps = [dep("vendor:Northwind", "vendor", owner="Vendor Operations", source_event_id="E1")]
    signal = infer_action(events, deps, "WAITING_FOR_VENDOR")
    assert signal.category == "VENDOR_RESPONSE"
    assert signal.evidence_ids == ["E1"]
    assert "replacement part" in signal.text.lower()


def test_customer_response_pending_action():
    events = [ev("E1", "WORK_NOTE", "Waiting on customer for the invoice copy.", 1)]
    signal = infer_action(events, [], "WAITING_FOR_CUSTOMER")
    assert signal.category == "CUSTOMER_RESPONSE"
    assert signal.evidence_ids == ["E1"]


def test_escalation_action():
    events = [ev("E1", "WORK_NOTE", "Raised SLA risk; escalating to the account manager.", 3)]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal.category == "ESCALATION"
    assert "escalated" in signal.text.lower()


def test_reassignment_action():
    events = [ev("E1", "TEAM_TRANSFER", "Handing off to the EMEA Support team.", 3, team="EMEA Support")]
    signal = infer_action(events, [], "TRANSFERRED")
    assert signal.category == "REASSIGNMENT"
    assert "reassigned" in signal.text.lower()


def test_investigation_action():
    events = [ev("E1", "WORK_NOTE", "Investigation into the sync failure continues.", 2)]
    signal = infer_action(events, [], "INVESTIGATING")
    assert signal.category == "INVESTIGATION"
    assert "investigation" in signal.text.lower()


def test_deployment_action():
    events = [ev("E1", "WORK_NOTE", "Patch deployment scheduled for the maintenance window.", 4)]
    signal = infer_action(events, [], "SCHEDULED")
    assert signal.category == "DEPLOYMENT"
    assert "deployment" in signal.text.lower()


def test_verification_action():
    events = [ev("E1", "WORK_NOTE", "Will verify the fix and retest after the change.", 5)]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal.category == "VERIFICATION"
    assert "verified" in signal.text.lower()


def test_closure_action():
    events = [ev("E1", "WORK_NOTE", "Customer happy; we will close the ticket today.", 6)]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal.category == "CLOSURE"
    assert "closed" in signal.text.lower()


# ----------------------------------------------------------------------
# 4. Most recent marker wins
# ----------------------------------------------------------------------
def test_latest_actionable_event_wins():
    events = [
        ev("E1", "WORK_NOTE", "Awaiting vendor confirmation on the shipment.", 1),
        ev("E2", "WORK_NOTE", "Patch deployment scheduled for the maintenance window.", 5),
    ]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal.category == "DEPLOYMENT"
    assert signal.evidence_ids == ["E2"]


def test_pre_resolution_markers_are_ignored():
    """A note written before the ticket was resolved must not drive a next action."""
    events = [
        ev("E1", "WORK_NOTE", "Awaiting vendor confirmation on the shipment.", 1),
        ev("E2", "RESOLUTION", "Issue resolved with the customer.", 4),
    ]
    assert infer_action(events, [], "RESOLVED") is None


# ----------------------------------------------------------------------
# 5. Sparse evidence must not invent an action
# ----------------------------------------------------------------------
def test_no_events_yields_no_action_signal():
    assert infer_action([], [], "IN_PROGRESS") is None


def test_single_unrelated_event_yields_safe_status_confirmation():
    events = [ev("E1", "STATUS_CHANGE", "Assigned to NA Support.", 1)]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal is not None
    assert signal.category == "STATUS_CONFIRMATION"
    assert signal.confidence == "sparse"
    assert signal.evidence_ids == ["E1"]


def test_status_confirmation_does_not_invent_specific_work():
    events = [ev("E1", "STATUS_CHANGE", "Assigned to NA Support.", 1)]
    text = infer_action(events, [], "IN_PROGRESS").text.lower()
    for invented in ("deploy", "patch", "approval", "vendor", "logs", "escalat"):
        assert invented not in text


def test_no_action_signal_when_events_are_plentiful_but_generic():
    events = [
        ev("E1", "STATUS_CHANGE", "Assigned to NA Support.", 1),
        ev("E2", "WORK_NOTE", "Ticket reviewed by the queue.", 2),
        ev("E3", "WORK_NOTE", "Notes updated.", 3),
    ]
    assert infer_action(events, [], "IN_PROGRESS") is None


# ----------------------------------------------------------------------
# 6. Conflicting evidence stays explainable
# ----------------------------------------------------------------------
def test_conflicting_notes_still_yield_one_explainable_action():
    events = [
        ev("E1", "WORK_NOTE", "Awaiting vendor confirmation on the shipment.", 1),
        ev("E2", "WORK_NOTE", "Escalating to the account manager for a decision.", 4,
           conflict_flag=True),
    ]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal is not None
    assert signal.evidence_ids == ["E2"]
    assert signal.reason  # the UI can show why this action was chosen


# ----------------------------------------------------------------------
# 7. Every signal is explainable
# ----------------------------------------------------------------------
def test_every_signal_carries_a_reason():
    events = [ev("E1", "WORK_NOTE", "Please provide logs from the affected host.", 1)]
    signal = infer_action(events, [], "IN_PROGRESS")
    assert signal.reason
    assert "WORK_NOTE" in signal.reason


def test_dependencies_feed_owner_and_detail():
    events = [ev("E1", "APPROVAL_REQUESTED", "Approval required before rollout.", 1,
                 approval_type="Procurement", team="EMEA Support")]
    deps = [dep("approval:procurement", "approval", owner="EMEA Support",
                title="Procurement approval", source_event_id="E1")]
    signal = infer_action(events, deps, "WAITING_FOR_APPROVAL")
    assert "EMEA Support" in signal.text
    assert "procurement" in signal.text.lower()


def test_category_templates_render_without_keyerror():
    """Every template must render with the slots the engine supplies."""
    for category in ACTION_CATEGORIES:
        text = category.template.format(owner="NA Support", detail="the replacement part")
        assert text and "{owner}" not in text and "{detail}" not in text


def test_category_lookup_table_is_consistent():
    for category in ACTION_CATEGORIES:
        assert CATEGORY_BY_KEY[category.key] is category
