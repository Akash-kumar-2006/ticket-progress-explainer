"""Human-validation framework tests.

IMPORTANT: these tests verify the *machinery* only. They create rows directly in
the test database to check the arithmetic of the agreement statistics. They are
NOT human validation results, and nothing here may be quoted as evidence that a
human panel has reviewed the system. The production table starts empty and
``summary()`` reports ``validation_completed = False`` until real reviewers
submit rows.
"""
from __future__ import annotations

import pytest

from backend.app.services.human_evaluation_service import (
    HumanEvaluationService,
    _cohens_kappa,
    _fleiss_kappa,
    _kappa_from_pairs,
)


@pytest.fixture
def svc(fresh_db):
    return HumanEvaluationService(fresh_db)


# ----------------------------------------------------------------------
# Framework state
# ----------------------------------------------------------------------
def test_summary_reports_not_completed_when_empty(svc):
    summary = svc.summary()
    assert summary["validation_completed"] is False
    assert summary["total_reviews"] == 0
    assert summary["acceptance_rate"] is None
    assert summary["inter_reviewer_agreement"] is None
    assert "framework ready" in summary["status"]


def test_no_human_reviews_exist_in_the_seeded_database(fresh_db):
    from backend.app.models.evaluation import HumanReview

    assert fresh_db.query(HumanReview).count() == 0


# ----------------------------------------------------------------------
# Review packet
# ----------------------------------------------------------------------
def test_packet_contains_ground_truth_and_generated_action(svc):
    packet = svc.build_packet(limit=5)
    assert len(packet) == 5
    for row in packet:
        assert row["ticket_id"]
        assert row["case_id"]
        assert "expected_action" in row
        assert "generated_action" in row
        assert row["generated_explanation"]


def test_packet_leaves_judgement_columns_blank(svc):
    packet = svc.build_packet(limit=3)
    for row in packet:
        for field in ("reviewer_id", "decision", "action_agrees", "understanding", "followup_required"):
            assert row[field] == "", f"{field} must be blank in the packet"


def test_packet_excludes_resolved_cases(svc):
    from backend.app.services.evaluation_service import EVALUATION_CSV
    import pandas as pd

    resolved = set(
        pd.read_csv(EVALUATION_CSV, keep_default_na=False)
        .query("expected_state == 'RESOLVED'")["ticket_id"]
    )
    for row in svc.build_packet(limit=12):
        assert row["ticket_id"] not in resolved


# ----------------------------------------------------------------------
# Submission validation
# ----------------------------------------------------------------------
def test_submit_stores_a_review(svc):
    row = svc.submit_review(
        case_id="E-001",
        ticket_id="DEMO-001",
        reviewer_id="R1",
        decision="ACCEPT",
        action_agrees=True,
        understanding=4,
        followup_required=False,
    )
    assert row.id is not None
    assert row.decision == "ACCEPT"


def test_submit_rejects_invalid_decision(svc):
    with pytest.raises(ValueError):
        svc.submit_review(
            case_id="E-001", ticket_id="DEMO-001", reviewer_id="R1",
            decision="MAYBE", action_agrees=True, understanding=3, followup_required=False,
        )


def test_submit_rejects_out_of_range_understanding(svc):
    with pytest.raises(ValueError):
        svc.submit_review(
            case_id="E-001", ticket_id="DEMO-001", reviewer_id="R1",
            decision="ACCEPT", action_agrees=True, understanding=9, followup_required=False,
        )


# ----------------------------------------------------------------------
# Agreement statistics
# ----------------------------------------------------------------------
def test_kappa_from_pairs_is_bounded():
    pairs = [(True, True), (True, True), (False, False), (False, True)]
    kappa = _kappa_from_pairs(pairs)
    assert 0.0 <= kappa <= 1.0


def test_kappa_from_empty_input_is_not_computable():
    assert _kappa_from_pairs([]) is None


def test_perfect_agreement_reports_one():
    assert _kappa_from_pairs([(True, True), (False, False)]) == 1.0


def test_disagreement_below_chance_is_reported_negative():
    # Reviewers systematically opposite -> kappa below zero.
    assert _kappa_from_pairs([(True, False), (False, True)]) < 0


def test_fleiss_kappa_needs_three_reviewers(svc):
    from backend.app.models.evaluation import HumanReview

    # Two cases with differing judgements keep kappa well defined (expected
    # agreement below 1.0). Two reviewers -> Cohen, not Fleiss.
    for case, reviewer, agrees in (
        ("E-001", "R1", True), ("E-001", "R2", True),
        ("E-002", "R1", False), ("E-002", "R2", False),
    ):
        svc.submit_review(case_id=case, ticket_id="T1", reviewer_id=reviewer,
                          decision="ACCEPT" if agrees else "REJECT",
                          action_agrees=agrees, understanding=4, followup_required=False)
    reviews = svc.db.query(HumanReview).all()
    assert _cohens_kappa(reviews) is not None
    assert _fleiss_kappa(reviews) is None


def test_kappa_helper_used_by_summary(svc):
    from backend.app.models.evaluation import HumanReview

    # Two cases with differing judgements keep kappa well defined.
    for case, reviewer, agrees in (
        ("E-001", "R1", True), ("E-001", "R2", True),
        ("E-002", "R1", False), ("E-002", "R2", True),
    ):
        svc.submit_review(
            case_id=case, ticket_id="T1", reviewer_id=reviewer,
            decision="ACCEPT" if agrees else "REJECT",
            action_agrees=agrees, understanding=4, followup_required=False,
        )
    reviews = svc.db.query(HumanReview).all()
    kappa = _cohens_kappa(reviews)
    assert kappa is not None and 0.0 <= kappa <= 1.0


def test_summary_switches_to_completed_once_reviews_exist(svc):
    for reviewer, agrees in (("R1", True), ("R2", True)):
        svc.submit_review(
            case_id="E-001", ticket_id="T1", reviewer_id=reviewer,
            decision="ACCEPT" if agrees else "REJECT",
            action_agrees=agrees, understanding=4, followup_required=False,
        )
    summary = svc.summary()
    assert summary["validation_completed"] is True
    assert summary["total_reviews"] == 2
    assert summary["cases_reviewed"] == 1
    # Both reviewers agreed on every case, so expected agreement is 1.0. The
    # framework reports perfect agreement as 1.0 rather than a misleading number.
    assert summary["agreement_statistic"] == "cohens_kappa"
    assert summary["inter_reviewer_agreement"] == 1.0
    assert summary["next_action_agreement"] == 1.0
    assert summary["acceptance_rate"] == 1.0
    assert summary["followup_rate"] == 0.0


def test_unanimous_agreement_yields_maximum_fleiss_kappa(svc):
    for reviewer in ("R1", "R2", "R3"):
        for case in ("E-001", "E-002", "E-003"):
            svc.submit_review(
                case_id=case, ticket_id="T1", reviewer_id=reviewer,
                decision="ACCEPT", action_agrees=True, understanding=4,
                followup_required=False,
            )
    summary = svc.summary()
    assert summary["agreement_statistic"] == "fleiss_kappa"
    assert summary["inter_reviewer_agreement"] == 1.0
    assert summary["cases_reviewed"] == 3


# ----------------------------------------------------------------------
# CSV round-trip
# ----------------------------------------------------------------------
def test_template_export_and_import_round_trip(svc, tmp_path):
    import csv as _csv

    rows = svc.build_packet(limit=2)
    csv_path = tmp_path / "reviews.csv"
    header = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        # one filled row, one blank row that must be ignored
        filled = dict(rows[0])
        filled.update(
            reviewer_id="R1", decision="ACCEPT", action_agrees="true",
            understanding="4", followup_required="false",
        )
        writer.writerow(filled)
        writer.writerow(rows[1])

    loaded = svc.import_csv(csv_path)
    assert loaded == 1
    assert svc.summary()["total_reviews"] == 1


def test_template_export_writes_blank_judgement_columns(svc, tmp_path, monkeypatch):
    from backend.app.services import human_evaluation_service as mod

    target = tmp_path / "human_review_template.csv"
    monkeypatch.setattr(mod, "HUMAN_TEMPLATE_CSV", target)
    svc.export_template(limit=3)
    assert target.exists()

    import csv as _csv

    with target.open(newline="", encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))
    assert len(rows) == 3
    for row in rows:
        assert row["reviewer_id"] == ""
        assert row["decision"] == ""
        assert row["generated_action"] or row["generated_explanation"]
