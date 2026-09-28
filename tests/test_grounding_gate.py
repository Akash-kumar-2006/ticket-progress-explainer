"""Grounding and refusal gate tests.

The gate is the safety net for *any* generator, including the optional LLM one.
These tests cover the six situations named in the review feedback and assert the
central property: the gate FAILS when an unsupported claim is detected.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.app.engines.models import Claim, EvidenceItem, ExplanationPayload, EventData
from backend.app.services.grounding_gate import (
    assert_grounded,
    check_grounding,
    refuses_without_evidence,
)

BASE = datetime(2026, 9, 1, 9, 0)


def ev(event_id: str, event_type: str, message: str = "", hours: int = 0, **extra) -> EventData:
    return EventData(
        event_id=event_id,
        ticket_id="T-1",
        timestamp=BASE + timedelta(hours=hours),
        event_type=event_type,
        message=message,
        **extra,
    )


def evidence(*events: EventData) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            event_id=e.event_id,
            event_type=e.event_type,
            timestamp=e.timestamp,
            text=e.message or e.event_type,
            reason="test",
        )
        for e in events
    ]


def payload(
    explanation: str,
    events: list[EventData],
    *,
    insufficient: bool = False,
    next_action: str = "",
    next_action_evidence: list[str] | None = None,
    claims: list[Claim] | None = None,
) -> ExplanationPayload:
    if claims is None:
        claims = [Claim(category="status", text=explanation, evidence=[events[0].event_id])]
    return ExplanationPayload(
        ticket_id="T-1",
        progress_state="IN_PROGRESS",
        effective_status="IN_PROGRESS",
        date_status=None,
        risk="low",
        grounding_score=80,
        explanation=explanation,
        claims=claims,
        evidence=evidence(*events),
        next_action=next_action or None,
        next_action_evidence=next_action_evidence or [],
        insufficient_evidence=insufficient,
    )


# ----------------------------------------------------------------------
# 1. Fully grounded ticket - gate passes
# ----------------------------------------------------------------------
def test_fully_grounded_ticket_passes():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("Your request is currently being handled by NA Support.", events)
    report = check_grounding(p, events)
    assert report.passed, report.violations


# ----------------------------------------------------------------------
# 2. Partially grounded ticket - gate passes
# ----------------------------------------------------------------------
def test_partially_grounded_ticket_passes():
    events = [
        ev("E1", "WORK_NOTE", "Waiting on customer for the invoice copy.", 0),
        ev("E2", "PROMISED_DATE_SET", "Promised date recorded.", 1),
    ]
    p = payload(
        "Your request is currently waiting on information from you. "
        "Your promised completion date is still achievable.",
        events,
        next_action="The customer must provide the requested information.",
        next_action_evidence=["E1"],
    )
    report = check_grounding(p, events)
    assert report.passed, report.violations


# ----------------------------------------------------------------------
# 3. Sparse ticket - gate passes and the system refuses
# ----------------------------------------------------------------------
def test_sparse_ticket_passes_with_explicit_refusal():
    events = [ev("E1", "STATUS_CHANGE", "")]
    p = payload(
        "Your ticket is currently in progress. The available updates do not provide "
        "enough information to reliably explain the next step.",
        events,
        insufficient=True,
    )
    report = check_grounding(p, events)
    assert report.passed, report.violations
    assert report.refused is True
    assert refuses_without_evidence(p)


# ----------------------------------------------------------------------
# 4. Conflicting ticket - conflict is reported, gate still passes
# ----------------------------------------------------------------------
def test_conflicting_ticket_is_reported_and_passes():
    events = [
        ev("E1", "STATUS_CHANGE", "Marked resolved.", 0, new_status="RESOLVED"),
        ev("E2", "STATUS_CHANGE", "Work resumed.", 2, new_status="IN_PROGRESS", conflict_flag=True),
    ]
    p = payload("Your request is currently being handled by NA Support.", events)
    report = check_grounding(p, events)
    assert report.passed, report.violations


# ----------------------------------------------------------------------
# 5. Unsupported claims - the gate must FAIL
# ----------------------------------------------------------------------
def test_invented_resolution_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.", new_status="IN_PROGRESS")]
    p = payload("Your request has been resolved.", events)
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "no_invented_completion" for v in report.violations)


def test_invented_date_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("Your request will be resolved by September 30.", events)
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "no_invented_date" for v in report.violations)


def test_invented_approval_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("The approval has been granted and work continues.", events)
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "no_invented_approval" for v in report.violations)


def test_invented_vendor_response_fails_the_gate():
    events = [ev("E1", "VENDOR_UPDATE", "Vendor will confirm shortly.")]
    p = payload("The vendor has shipped the replacement and it will arrive soon.", events)
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "no_invented_vendor" for v in report.violations)


def test_invented_customer_contact_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("We have emailed you with an update.", events)
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "no_invented_customer_contact" for v in report.violations)


def test_claim_without_evidence_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload(
        "Your request is being handled by NA Support.",
        events,
        claims=[Claim(category="status", text="A claim with no source.", evidence=[], supported=False)],
    )
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "claims_have_evidence" for v in report.violations)


def test_claim_citing_an_unknown_event_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload(
        "Your request is being handled by NA Support.",
        events,
        claims=[Claim(category="status", text="Cites a missing event.", evidence=["E-DOES-NOT-EXIST"])],
    )
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "evidence_exists_on_ticket" for v in report.violations)


def test_next_action_citing_an_unknown_event_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload(
        "Your request is being handled by NA Support.",
        events,
        next_action="The vendor must ship the part.",
        next_action_evidence=["E-NOPE"],
    )
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "next_action_evidence_exists" for v in report.violations)


# ----------------------------------------------------------------------
# 6. Missing evidence - refusal must not state a confident action
# ----------------------------------------------------------------------
def test_confident_action_while_unsure_fails_the_gate():
    events = [ev("E1", "STATUS_CHANGE", "")]
    p = payload(
        "Your ticket is currently in progress. The available updates do not provide "
        "enough information to reliably explain the next step.",
        events,
        insufficient=True,
        next_action="The vendor must ship the replacement part.",
        next_action_evidence=["E1"],
    )
    report = check_grounding(p, events)
    assert not report.passed
    assert any(v["check"] == "no_confident_action_when_unsure" for v in report.violations)


def test_status_confirmation_action_is_allowed_while_unsure():
    events = [ev("E1", "STATUS_CHANGE", "")]
    p = payload(
        "Your ticket is currently in progress. The available updates do not provide "
        "enough information to reliably explain the next step.",
        events,
        insufficient=True,
        next_action="The support team is confirming the current status.",
        next_action_evidence=["E1"],
    )
    report = check_grounding(p, events)
    assert report.passed, report.violations


def test_ticket_with_no_events_passes_only_with_a_refusal():
    p = ExplanationPayload(
        ticket_id="T-1",
        progress_state="INVESTIGATING",
        effective_status="OPEN",
        date_status=None,
        risk="unknown",
        grounding_score=0,
        explanation=(
            "Your ticket is currently in progress. The available updates do not provide "
            "enough information to reliably explain the next step."
        ),
        claims=[],
        evidence=[],
        insufficient_evidence=True,
    )
    report = check_grounding(p, [])
    assert report.passed, report.violations
    assert report.refused


# ----------------------------------------------------------------------
# 7. assert_grounded raises for CI
# ----------------------------------------------------------------------
def test_assert_grounded_raises_on_violation():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("Your request has been resolved.", events)
    with pytest.raises(AssertionError):
        assert_grounded(p, events)


def test_assert_grounded_passes_for_clean_output():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("Your request is currently being handled by NA Support.", events)
    assert assert_grounded(p, events).passed


def test_report_is_serialisable():
    events = [ev("E1", "STATUS_CHANGE", "Work in progress.")]
    p = payload("Your request has been resolved.", events)
    data = check_grounding(p, events).to_dict()
    assert set(data) == {"passed", "refused", "checks", "violations"}
    assert isinstance(data["violations"], list)
