"""Date Risk engine tests."""
from datetime import datetime, timedelta

from backend.app.engines.date_risk import DateRiskEngine

REF = datetime(2026, 9, 7, 12, 0)


def test_on_track():
    r = DateRiskEngine().analyze(REF + timedelta(days=5), False, "IN_PROGRESS", [], REF)
    assert r.date_status == "ON_TRACK"
    assert r.days_remaining == 5


def test_at_risk_when_waiting_close_to_date():
    r = DateRiskEngine().analyze(REF + timedelta(days=2), False, "WAITING_FOR_VENDOR", [], REF)
    assert r.date_status == "AT_RISK"


def test_at_risk_from_vendor_delay_evidence():
    from backend.app.engines.models import EventData

    evt = EventData(
        event_id="E1", ticket_id="T", timestamp=REF, event_type="VENDOR_UPDATE",
        message="parts will arrive late",
    )
    r = DateRiskEngine().analyze(REF + timedelta(days=10), False, "IN_PROGRESS", [evt], REF)
    assert r.date_status == "AT_RISK"
    assert r.delay_evidence_ids == ["E1"]


def test_overdue():
    r = DateRiskEngine().analyze(REF - timedelta(days=3), False, "IN_PROGRESS", [], REF)
    assert r.date_status == "OVERDUE"
    assert r.overdue_days == 3


def test_completed_when_resolved():
    r = DateRiskEngine().analyze(REF, True, "RESOLVED", [], REF)
    assert r.date_status == "COMPLETED"


def test_no_promised_date():
    r = DateRiskEngine().analyze(None, False, "OPEN", [], REF)
    assert r.date_status is None
    assert r.days_remaining is None