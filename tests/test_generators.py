"""Generator-level tests: evidence grounding and anti-hallucination guards."""
from backend.app.database import SessionLocal
from backend.app.services.explanation_service import ExplanationService


def payload(tid, generator="rule_based"):
    db = SessionLocal()
    try:
        return ExplanationService(db).generate(tid, generator, persist=False)[0]
    finally:
        db.close()


def test_demo_tickets_have_expected_states():
    expected = {
        "DEMO-001": "SCHEDULED",
        "DEMO-002": "WAITING_FOR_APPROVAL",
        "DEMO-003": "WAITING_FOR_VENDOR",
        "DEMO-004": "DELAYED",
        "DEMO-005": "IN_PROGRESS",
        "DEMO-006": "INVESTIGATING",
        "DEMO-007": "REOPENED",
    }
    for tid, state in expected.items():
        p = payload(tid)
        assert p.progress_state == state, f"{tid}: expected {state}, got {p.progress_state}"


def test_every_sentence_is_supported_by_evidence():
    for tid in ("DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004", "DEMO-005"):
        p = payload(tid)
        # every claim in the output must cite at least one real event
        for claim in p.claims:
            assert claim.supported, f"{tid}: unsupported claim leaked into output: {claim.text}"
            assert claim.evidence, f"{tid}: claim with empty evidence: {claim.text}"
        # referenced events must actually exist for the ticket
        ev_ids = {e.event_id for e in p.evidence}
        for claim in p.claims:
            for eid in claim.evidence:
                assert eid in ev_ids


def test_known_factual_claims_present():
    p1 = payload("DEMO-001")
    assert "India Support" in p1.explanation
    assert "September 12" in p1.explanation  # promised date rendered from real event

    p3 = payload("DEMO-003")
    assert "Vendor Operations" in p3.explanation
    assert "parts" in p3.explanation.lower()

    p5 = payload("DEMO-005")
    assert p5.conflicts, "conflict ticket must report conflict"


def test_insufficient_evidence_yields_explicit_uncertainty_only():
    p6 = payload("DEMO-006")
    assert p6.insufficient_evidence is True
    assert "enough information" in p6.explanation.lower()


def test_no_hallucinated_resolution():
    """A ticket that has not been resolved must never claim resolution."""
    for tid in ("DEMO-003", "DEMO-004", "DEMO-005"):
        p = payload(tid)
        assert p.progress_state != "RESOLVED"
        assert "has been resolved" not in p.explanation.lower()


def test_next_action_has_evidence():
    for tid in ("DEMO-002", "DEMO-003", "DEMO-004"):
        p = payload(tid)
        assert p.next_action
        assert p.next_action_evidence


def test_baseline_generator_is_status_only():
    b = payload("DEMO-003", "baseline")
    assert b.is_baseline is True
    assert "vendor" not in b.explanation.lower()  # status-only: no dependency detail


def test_prototype_scored_against_readable_output():
    p = payload("DEMO-003")
    assert p.grounding_score >= 60
    # claims visible to users: state + blocker + next action + date
    cats = {c.category for c in p.claims}
    assert {"status", "blocker", "next_action", "date"} <= cats