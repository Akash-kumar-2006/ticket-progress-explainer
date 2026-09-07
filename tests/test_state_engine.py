"""Progress State Engine tests using synthetic ticket fixtures for every state."""
from datetime import datetime, timedelta

import pytest

from backend.app.engines.dependency import DependencyEngine
from backend.app.engines.models import EventData
from backend.app.engines.state import ProgressStateEngine

REF = datetime(2026, 9, 7, 12, 0)


def ev(eid, etype, ts, **kw):
    return EventData(event_id=eid, ticket_id="T", timestamp=ts, event_type=etype, **kw)


def analyze(events, status="OPEN", promised=None):
    deps = DependencyEngine().build(events)
    return ProgressStateEngine().analyze(
        ticket_id="T",
        ticket_status=status,
        promised_date=promised,
        events=events,
        deps=deps,
        now=REF,
    )


def test_resolved_state_from_resolution_event():
    p = analyze(
        [
            ev("EV-1", "STATUS_CHANGE", REF - timedelta(days=3), new_status="IN_PROGRESS"),
            ev("EV-2", "RESOLUTION", REF - timedelta(days=1)),
        ],
        promised=REF,
    )
    assert p.progress_state == "RESOLVED"
    assert p.date_status == "COMPLETED"


def test_waiting_for_approval():
    p = analyze(
        [
            ev("EV-1", "STATUS_CHANGE", REF - timedelta(days=3), new_status="IN_PROGRESS"),
            ev("EV-2", "APPROVAL_REQUESTED", REF - timedelta(days=2), approval_type="Security approval"),
            ev("EV-3", "DEPENDENCY_CREATED", REF - timedelta(days=2), dependency_id="approval:security"),
        ],
        promised=REF + timedelta(days=5),
    )
    assert p.progress_state == "WAITING_FOR_APPROVAL"
    assert p.waiting_on


def test_waiting_for_vendor_with_prefix_dependency():
    p = analyze(
        [
            ev("EV-1", "DEPENDENCY_CREATED", REF - timedelta(days=2),
               dependency_id="vendor:PartsUnited Express", dependency_owner="Vendor Operations"),
            ev("EV-2", "VENDOR_UPDATE", REF - timedelta(days=1), vendor="PartsUnited Express",
               message="waiting for stock"),
        ],
        promised=REF + timedelta(days=3),
    )
    assert p.progress_state == "WAITING_FOR_VENDOR"


def test_blocked_when_vendor_dependency_blocked():
    p = analyze(
        [
            ev("EV-1", "DEPENDENCY_CREATED", REF - timedelta(days=2),
               dependency_id="vendor:PartsUnited Express", dependency_owner="Vendor Operations"),
            ev("EV-2", "DEPENDENCY_BLOCKED", REF - timedelta(days=1),
               dependency_id="vendor:PartsUnited Express"),
        ],
    )
    assert p.progress_state == "BLOCKED"


def test_delayed_when_overdue_no_wait_dependency():
    p = analyze(
        [
            ev("EV-1", "STATUS_CHANGE", REF - timedelta(days=6), new_status="IN_PROGRESS"),
            ev("EV-2", "WORK_NOTE", REF - timedelta(days=5), message="still working"),
        ],
        promised=REF - timedelta(days=2),
    )
    assert p.progress_state == "DELAYED"
    assert p.date_status == "OVERDUE"
    assert p.overdue_days >= 2


def test_investigating_for_open_ticket():
    p = analyze([ev("EV-1", "ASSIGNMENT_CHANGE", REF - timedelta(hours=2))])
    assert p.progress_state == "INVESTIGATING"


def test_reopened_after_resolution():
    p = analyze(
        [
            ev("EV-1", "RESOLUTION", REF - timedelta(days=2)),
            ev("EV-2", "REOPENED", REF - timedelta(hours=5)),
        ],
        promised=REF + timedelta(days=2),
    )
    assert p.progress_state == "REOPENED"


def test_conflict_flag_surfaced_for_resolved_then_in_progress():
    p = analyze(
        [
            ev("EV-1", "STATUS_CHANGE", REF - timedelta(days=2), new_status="RESOLVED"),
            ev("EV-2", "STATUS_CHANGE", REF - timedelta(hours=3), new_status="IN_PROGRESS"),
        ],
    )
    assert any("conflict" in r.lower() for r in p.reasons)


def test_effective_status_prefers_latest_valid_terminal_event():
    events = [
        ev("EV-1", "STATUS_CHANGE", REF - timedelta(days=2), new_status="RESOLVED"),
        ev("EV-2", "STATUS_CHANGE", REF - timedelta(hours=3), new_status="IN_PROGRESS"),
    ]
    assert ProgressStateEngine.effective_status("RESOLVED", events) == "IN_PROGRESS"


def test_transferred_shortly_after_team_transfer():
    p = analyze(
        [
            ev("EV-1", "STATUS_CHANGE", REF - timedelta(days=4), new_status="IN_PROGRESS"),
            ev("EV-2", "TEAM_TRANSFER", REF - timedelta(hours=10)),
        ],
    )
    assert p.progress_state == "TRANSFERRED"


def test_unsupported_literal_never_injected():
    """The state engine names states from a fixed enumeration - a safety net
    proving unknown statuses cannot produce fabricated labels."""
    p = analyze([ev("EV-1", "WORK_NOTE", REF - timedelta(days=1), message="we will resolve tomorrow")])
    assert p.progress_state in {
        "RESOLVED", "REOPENED", "WAITING_FOR_APPROVAL", "WAITING_FOR_VENDOR",
        "WAITING_FOR_CUSTOMER", "WAITING_FOR_INTERNAL_TEAM", "BLOCKED", "DELAYED",
        "TRANSFERRED", "IN_PROGRESS", "INVESTIGATING", "SCHEDULED",
    }