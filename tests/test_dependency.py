"""Dependency engine tests: kinds, status resolution, age tracking."""
from datetime import datetime, timedelta

from backend.app.engines.dependency import DependencyEngine
from backend.app.engines.models import EventData

REF = datetime(2026, 9, 7, 12, 0)


def ev(eid, etype, ts, **kw):
    return EventData(event_id=eid, ticket_id="T", timestamp=ts, event_type=etype, **kw)


def test_dependency_kind_resolution():
    e = DependencyEngine()

    deps = e.build([
        ev("E-a", "APPROVAL_REQUESTED", REF, approval_type="Security Review"),
        ev("E-b", "DEPENDENCY_CREATED", REF, dependency_id="approval:finance"),
        ev("E-v", "DEPENDENCY_CREATED", REF, dependency_id="vendor:Acme"),
        ev("E-i", "DEPENDENCY_CREATED", REF, dependency_id="DB-migration", dependency_owner="DBA Team"),
    ])
    kinds = {d.dependency_id: d.kind for d in deps}
    assert kinds["approval:finance"] == "approval"
    assert kinds["vendor:Acme"] == "vendor"
    assert kinds["approval:Security Review"] == "approval"
    assert kinds["DB-migration"] == "internal"


def test_pending_then_completed_when_dependency_completed_event_seen():
    deps = DependencyEngine().build([
        ev("E-a", "DEPENDENCY_CREATED", REF - timedelta(days=2), dependency_id="vendor:Acme"),
        ev("E-b", "DEPENDENCY_COMPLETED", REF, dependency_id="vendor:Acme"),
    ])
    by_id = {d.dependency_id: d for d in deps}
    assert by_id["vendor:Acme"].status == "completed"
    assert by_id["vendor:Acme"].completed_at is not None
    assert by_id["vendor:Acme"].age_days is not None


def test_blocked_dependency():
    deps = DependencyEngine().build([
        ev("E-a", "DEPENDENCY_CREATED", REF, dependency_id="vendor:Acme"),
        ev("E-b", "DEPENDENCY_BLOCKED", REF, dependency_id="vendor:Acme"),
    ])
    assert {d.dependency_id: d.status for d in deps}["vendor:Acme"] == "blocked"


def test_incomplete_filter():
    deps = DependencyEngine().build([
        ev("E-a", "DEPENDENCY_CREATED", REF, dependency_id="approval:sec"),
        ev("E-b", "DEPENDENCY_COMPLETED", REF, dependency_id="Vendor ops"),
        ev("E-c", "DEPENDENCY_CREATED", REF, dependency_id="vendor:Parts"),
    ])
    assert {d.dependency_id for d in DependencyEngine.incomplete(deps, "approval")} == {"approval:sec"}
    assert {d.dependency_id for d in DependencyEngine.incomplete(deps, "vendor")} == {"vendor:Parts"}