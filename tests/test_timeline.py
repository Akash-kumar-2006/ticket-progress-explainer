"""Engine-level tests for the timeline engine."""
from datetime import datetime, timedelta

from backend.app.engines.models import EventData
from backend.app.engines.timeline import TimelineEngine
from backend.app.config import PROJECT_ROOT


def make_ev(eid, ts, etype, **kw):
    return EventData(
        event_id=eid,
        ticket_id="T",
        timestamp=ts,
        event_type=etype,
        **kw,
    )


def test_orders_chronologically():
    t0 = datetime(2026, 9, 1, 8, 0)
    evs = [
        make_ev("EV-3", t0 + timedelta(days=2), "WORK_NOTE"),
        make_ev("EV-1", t0, "STATUS_CHANGE"),
        make_ev("EV-2", t0 + timedelta(days=1), "WORK_NOTE"),
    ]
    tl = TimelineEngine().build(evs, t0)
    ids = [e.event_id for e in tl.entries]
    assert ids == ["EV-1", "EV-2", "EV-3"]
    assert tl.total == 3


def test_duplicate_and_out_of_order_flags_line_up_with_dataset():
    tl = TimelineEngine().build(
        [
            make_ev("EV-01020", datetime(2026, 9, 5, 9, 0), "WORK_NOTE", is_duplicate=True),
            make_ev("EV-01017", datetime(2026, 9, 1, 9, 0), "WORK_NOTE", is_out_of_order=True),
        ],
        datetime(2026, 8, 1),
    )
    assert tl.duplicates == ["EV-01020"]
    assert tl.out_of_order == ["EV-01017"]


def test_dataset_timeline_flags_conflicts():
    from backend.app.database import SessionLocal
    from backend.app.services.explanation_service import ExplanationService

    db = SessionLocal()
    try:
        svc = ExplanationService(db)
        for tid in ("DEMO-005",):
            tl = svc.timeline(tid)
        assert tl.conflicts, "conflict ticket should report conflicts"
        for e in tl.entries:
            assert isinstance(e.index, int)
    finally:
        db.close()


def test_projects_root_anchored():
    assert (PROJECT_ROOT / "data").exists()