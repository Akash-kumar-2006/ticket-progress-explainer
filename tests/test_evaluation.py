"""Evaluation suite: deterministic synthetic reviewer rules and API wiring."""
import pytest

from backend.app.database import SessionLocal
from backend.app.services.evaluation_service import EvaluationService


@pytest.fixture(scope="module")
def evaluation_run():
    db = SessionLocal()
    try:
        return EvaluationService(db).run()
    finally:
        db.close()


def test_run_evaluates_all_cases(evaluation_run):
    out = evaluation_run
    m = out["metrics"]
    assert out["num_cases"] == 64
    assert set(m) >= {
        "baseline_mean_understanding",
        "prototype_mean_understanding",
        "baseline_followup_rate",
        "prototype_followup_rate",
        "state_accuracy",
        "blocker_accuracy",
        "next_action_accuracy",
        "promised_date_accuracy",
        "grounding_accuracy",
    }


def test_prototype_beats_baseline(evaluation_run):
    m = evaluation_run["metrics"]
    assert m["prototype_mean_understanding"] > m["baseline_mean_understanding"]
    assert m["prototype_followup_rate"] < m["baseline_followup_rate"]


def test_each_result_contains_explanations(evaluation_run):
    results = evaluation_run["results"]
    assert len(results) == 64
    for r in results:
        assert r["prototype_explanation"]
        assert r["baseline_explanation"]
        assert isinstance(r["prototype_followup"], bool)
        assert r["grounding_score"] is not None


def test_api_evaluation_summary(client, evaluation_run):
    r = client.get("/api/evaluation/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["has_run"] is True
    assert body["num_cases"] == 64


def test_api_evaluation_results_listing(client, evaluation_run):
    r = client.get("/api/evaluation/results")
    assert r.status_code == 200
    items = r.json()["results"]
    assert isinstance(items, list) and items