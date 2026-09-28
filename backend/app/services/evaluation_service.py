"""Evaluation service.

Runs the BASELINE vs EVIDENCE-GROUNDED experiment over the evaluation case
database. Reviewer answers are simulated with a deterministic, documented
scoring rule (this is explicitly a *synthetic evaluation*). Human validation
rows are stored separately when provided (see docs/VALIDATION.md).

Synthetic reviewer rule (documented, reproducible):
  prototype_understanding = 1 + state_match + blocker_match + next_action_match + date_match
  prototype_followup      = prototype_understanding < 4
  baseline_understanding  = 1 + baseline_state_match + baseline_date_completed_match
  baseline_followup       = baseline_understanding < 3
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..config import PROJECT_ROOT
from ..models.evaluation import EvaluationResult, ExperimentRun
from .explanation_service import ExplanationService

EVALUATION_CSV = PROJECT_ROOT / "data" / "evaluation" / "evaluation_cases.csv"

STATE_KEYWORDS = {
    "WAITING_FOR_APPROVAL": "approval",
    "WAITING_FOR_VENDOR": "vendor",
    "WAITING_FOR_CUSTOMER": "customer",
    "WAITING_FOR_INTERNAL_TEAM": "waiting",
    "BLOCKED": "block",
    "DELAYED": "delay",
    "TRANSFERRED": "transfer",
    "IN_PROGRESS": "in progress",
    "INVESTIGATING": "investigat",
    "SCHEDULED": "scheduled",
    "RESOLVED": "resolved",
    "REOPENED": "reopen",
    "NEW": "new",
}


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.service = ExplanationService(db)

    def run(self, cases: list[dict] | None = None, as_of=None) -> dict:
        if cases is None:
            cases = self._load_cases()
        results = []
        for case in cases:
            results.append(self._score_case(case, as_of))

        metrics = _aggregate(results)
        run = ExperimentRun(
            run_at=datetime.now(timezone.utc),
            evaluation_type="synthetic",
            num_cases=len(results),
            **metrics,
        )
        self.db.add(run)
        self.db.flush()
        for r in results:
            rec = EvaluationResult(experiment_run_id=run.id, **r)
            self.db.add(rec)
        log_audit(
            self.db,
            actor="evaluator",
            role="ADMIN",
            action="EXPERIMENT_RUN",
            new_value=f"{len(results)} cases, prototype_understanding={metrics['prototype_mean_understanding']:.2f}",
            reason="synthetic evaluation (deterministic reviewer rules)",
            source="evaluation_service",
        )
        self.db.commit()
        run_dict = run.to_dict()
        run_dict["results"] = results
        run_dict["metrics"] = metrics
        self._update_csv_scores(results)
        return run_dict

    # ------------------------------------------------------------------
    def _score_case(self, case: dict, as_of=None) -> dict:
        ticket_id = case["ticket_id"]
        expected_state = case["expected_state"]
        expected_blocker = str(case.get("expected_blocker") or "")
        expected_next = str(case.get("expected_next_action") or "")
        expected_category = str(case.get("expected_action_category") or "").upper()
        expected_date = case.get("expected_date_status") or ""

        baseline_payload, _ = self.service.generate(ticket_id, "baseline", as_of, persist=False)
        proto_payload, _ = self.service.generate(ticket_id, "rule_based", as_of, persist=False)

        p_state = _matches_state(proto_payload.progress_state, expected_state)
        p_block = _mentions(proto_payload.explanation, expected_blocker) if expected_blocker else True
        p_date = bool(expected_date) and proto_payload.date_status == expected_date

        # Next action is scored on the action CATEGORY, which is derived
        # structurally (event types / dependency kinds) in the case builder and
        # is therefore independent of the marker lexicon the system uses. The old
        # free-text comparison is kept as a secondary signal only, because the
        # expected sentence is produced by the same engine as the output and can
        # therefore never be an independent measurement.
        p_text = _mentions(proto_payload.explanation, expected_next) if expected_next else True
        category_scored = expected_category not in ("", "UNSPECIFIED")
        p_category = proto_payload.next_action_category or ""
        p_next = (p_category == expected_category) if category_scored else p_text

        p_understanding = 1 + int(p_state) + int(p_block) + int(p_next) + int(p_date)
        p_followup = p_understanding < 4

        b_state = _baseline_state_match(baseline_payload.effective_status, expected_state)
        b_date = (expected_date == "COMPLETED" and baseline_payload.effective_status == "RESOLVED")
        b_understanding = 1 + int(b_state) + int(b_date)
        b_followup = b_understanding < 3

        return {
            "case_id": case["case_id"],
            "ticket_id": ticket_id,
            "expected_state": expected_state,
            "expected_date_status": expected_date,
            "difficulty": case.get("difficulty", "normal"),
            "failure_case": case.get("failure_case", "none"),
            "baseline_explanation": baseline_payload.explanation,
            "prototype_explanation": proto_payload.explanation,
            "baseline_understanding": float(b_understanding),
            "prototype_understanding": float(p_understanding),
            "baseline_followup": bool(b_followup),
            "prototype_followup": bool(p_followup),
            "state_match": bool(p_state),
            "blocker_match": bool(p_block),
            "next_action_match": bool(p_next),
            "date_match": bool(p_date),
            "grounding_score": float(proto_payload.grounding_score),
            "grounding_ok": bool(proto_payload.grounding_score >= 60),
            "next_action_category": p_category,
            "expected_action_category": expected_category,
            "next_action_category_scored": bool(category_scored),
            "next_action_text_match": bool(p_text),
        }

    @staticmethod
    def _load_cases() -> list[dict]:
        if not EVALUATION_CSV.exists():
            raise FileNotFoundError(f"evaluation cases not found at {EVALUATION_CSV}")
        df = pd.read_csv(EVALUATION_CSV, keep_default_na=False)
        return df.to_dict(orient="records")

    @staticmethod
    def _update_csv_scores(results: list[dict]) -> None:
        if not EVALUATION_CSV.exists():
            return
        df = pd.read_csv(EVALUATION_CSV, keep_default_na=False)
        by_case = {str(r["case_id"]): r for r in results}
        df["baseline_score"] = [
            str(by_case.get(str(c), {}).get("baseline_understanding", "")) for c in df["case_id"]
        ]
        df["prototype_score"] = [
            str(by_case.get(str(c), {}).get("prototype_understanding", "")) for c in df["case_id"]
        ]
        df.to_csv(EVALUATION_CSV, index=False)


def _matches_state(got: str, expected: str) -> bool:
    return got == expected


def _mentions(text: str, token: str) -> bool:
    if not token:
        return True
    return str(token).strip().lower() in text.lower()


def _baseline_state_match(baseline_status: str, expected_state: str) -> bool:
    if expected_state == "RESOLVED":
        return baseline_status == "RESOLVED"
    if expected_state in ("WAITING_FOR_APPROVAL", "WAITING_FOR_VENDOR", "WAITING_FOR_CUSTOMER",
                          "WAITING_FOR_INTERNAL_TEAM", "BLOCKED", "DELAYED", "TRANSFERRED",
                          "IN_PROGRESS", "INVESTIGATING", "SCHEDULED", "REOPENED", "NEW"):
        # Baseline only conveys broad status, so only match broad categories.
        return baseline_status in ("OPEN", "IN_PROGRESS", "PENDING", "ESCALATED")
    return False


def _aggregate(results: list[dict]) -> dict:
    n = max(1, len(results))
    b_mean = sum(r["baseline_understanding"] for r in results) / n
    p_mean = sum(r["prototype_understanding"] for r in results) / n
    b_fu = sum(1 for r in results if r["baseline_followup"])
    p_fu = sum(1 for r in results if r["prototype_followup"])
    blocker_cases = [r for r in results if r["expected_state"] != "RESOLVED" and _has_blocker(r)]
    next_cases = [r for r in results if r["expected_state"] != "RESOLVED"]
    category_cases = [
        r for r in next_cases
        if r.get("next_action_category_scored")
        and r.get("expected_action_category") not in ("", "UNSPECIFIED")
    ]
    return {
        "baseline_mean_understanding": round(b_mean, 3),
        "prototype_mean_understanding": round(p_mean, 3),
        "understanding_improvement_abs": round(p_mean - b_mean, 3),
        "understanding_improvement_pct": round((p_mean - b_mean) / max(b_mean, 1e-9) * 100.0, 1),
        "baseline_followup_rate": round(b_fu / n, 3),
        "prototype_followup_rate": round(p_fu / n, 3),
        "followup_reduction_pct": round((b_fu - p_fu) / max(b_fu, 1e-9) * 100.0, 1),
        "state_accuracy": round(sum(1 for r in results if r["state_match"]) / n, 3),
        "blocker_accuracy": round(sum(1 for r in blocker_cases if r["blocker_match"]) / max(len(blocker_cases), 1), 3),
        "next_action_accuracy": round(sum(1 for r in next_cases if r["next_action_match"]) / max(len(next_cases), 1), 3),
        "next_action_category_accuracy": round(
            sum(1 for r in category_cases if r["next_action_match"]) / max(len(category_cases), 1), 3
        ),
        "next_action_category_scored_cases": len(category_cases),
        "next_action_text_match_rate": round(
            sum(1 for r in next_cases if r.get("next_action_text_match")) / max(len(next_cases), 1), 3
        ),
        "promised_date_accuracy": round(sum(1 for r in results if r["date_match"]) / n, 3),
        "grounding_accuracy": round(sum(1 for r in results if r["grounding_ok"]) / n, 3),
    }


def _has_blocker(r: dict) -> bool:
    # A case is "blocker applicable" if the ticket state implies a waiting/blocked condition
    return r["expected_state"] in (
        "WAITING_FOR_APPROVAL", "WAITING_FOR_VENDOR", "WAITING_FOR_CUSTOMER",
        "WAITING_FOR_INTERNAL_TEAM", "BLOCKED", "DELAYED",
    )