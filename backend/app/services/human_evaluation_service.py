"""Lightweight human-validation framework.

The synthetic evaluation in :mod:`evaluation_service` uses deterministic reviewer
rules. Those rules are reproducible and free, but they are not people, so they
cannot show that a real customer or support agent would find an explanation
clear. This module provides the machinery to collect that evidence from a small
panel of reviewers (3-5) without pretending the panel already exists.

Status: FRAMEWORK READY, NO DATA COLLECTED. ``human_reviews`` starts empty and
``summary()`` reports ``validation_completed = False`` until rows arrive.

Statistics are implemented in plain Python so the project keeps its "no extra
dependencies" property (no scipy / scikit-learn):

* acceptance rate          - share of reviews with decision ACCEPT
* next-action agreement    - share of reviews where action_agrees is true
* inter-reviewer agreement - Cohen's kappa (exactly 2 reviewers) or Fleiss' kappa
                             (3 or more) on the binary "action agrees" item

How to use it
-------------
1. ``build_packet()`` produces a small, balanced sample of cases with the
   ground-truth expected action and the generated action, ready to hand out.
2. Each reviewer submits one row per case via ``submit_review()`` (or the CSV
   template, which is loaded back with ``import_csv()``).
3. ``summary()`` reports agreement statistics and flips
   ``validation_completed`` to True.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from ..config import PROJECT_ROOT
from ..models.evaluation import HumanReview
from .explanation_service import ExplanationService

HUMAN_TEMPLATE_CSV = PROJECT_ROOT / "data" / "evaluation" / "human_review_template.csv"

DECISIONS = ("ACCEPT", "REJECT", "UNCLEAR")


class HumanEvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.explanations = ExplanationService(db)

    # ------------------------------------------------------------------
    def build_packet(self, limit: int = 12, cases_csv: Path | None = None) -> list[dict]:
        """Return review rows: ground truth vs generated output, no judgements."""
        csv_path = cases_csv or (PROJECT_ROOT / "data" / "evaluation" / "evaluation_cases.csv")
        if not csv_path.exists():
            return []
        df = pd.read_csv(csv_path, keep_default_na=False)
        df = df[df["expected_state"] != "RESOLVED"]
        rows: list[dict] = []
        for _, case in df.iterrows():
            ticket_id = str(case["ticket_id"])
            payload, _ = self.explanations.generate(ticket_id, "rule_based", persist=False)
            rows.append(
                {
                    "case_id": str(case["case_id"]),
                    "ticket_id": ticket_id,
                    "expected_state": str(case["expected_state"]),
                    "expected_action": str(case.get("expected_action_category") or ""),
                    "expected_action_text": str(case.get("expected_next_action") or ""),
                    "generated_action": payload.next_action or "",
                    "generated_action_category": payload.next_action_category or "",
                    "generated_explanation": payload.explanation,
                    "grounding_score": int(payload.grounding_score),
                    # left blank on purpose: these are filled in by a human
                    "reviewer_id": "",
                    "decision": "",
                    "action_agrees": "",
                    "understanding": "",
                    "followup_required": "",
                    "comment": "",
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def export_template(self, limit: int = 12) -> Path:
        """Write the blank review sheet handed to reviewers."""
        rows = self.build_packet(limit=limit)
        HUMAN_TEMPLATE_CSV.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            return HUMAN_TEMPLATE_CSV
        with HUMAN_TEMPLATE_CSV.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return HUMAN_TEMPLATE_CSV

    # ------------------------------------------------------------------
    def submit_review(
        self,
        *,
        case_id: str,
        ticket_id: str,
        reviewer_id: str,
        decision: str,
        action_agrees: bool,
        understanding: int,
        followup_required: bool,
        expected_action: str = "",
        generated_action: str = "",
        comment: str = "",
    ) -> HumanReview:
        decision = (decision or "").upper()
        if decision not in DECISIONS:
            raise ValueError(f"decision must be one of {DECISIONS}")
        if not 1 <= int(understanding) <= 5:
            raise ValueError("understanding must be between 1 and 5")
        row = HumanReview(
            case_id=case_id,
            ticket_id=ticket_id,
            reviewer_id=reviewer_id,
            expected_action=expected_action,
            generated_action=generated_action,
            decision=decision,
            action_agrees=bool(action_agrees),
            understanding=int(understanding),
            followup_required=bool(followup_required),
            comment=comment or "",
            submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def import_csv(self, path: Path) -> int:
        """Load a filled-in review sheet. Rows with a blank reviewer_id are skipped."""
        if not path.exists():
            raise FileNotFoundError(str(path))
        loaded = 0
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if not str(row.get("reviewer_id", "")).strip():
                    continue
                self.submit_review(
                    case_id=str(row.get("case_id", "")),
                    ticket_id=str(row.get("ticket_id", "")),
                    reviewer_id=str(row["reviewer_id"]).strip(),
                    decision=str(row.get("decision", "")),
                    action_agrees=str(row.get("action_agrees", "")).strip().lower()
                    in ("true", "1", "yes", "y"),
                    understanding=int(row.get("understanding") or 0),
                    followup_required=str(row.get("followup_required", "")).strip().lower()
                    in ("true", "1", "yes", "y"),
                    expected_action=str(row.get("expected_action", "")),
                    generated_action=str(row.get("generated_action", "")),
                    comment=str(row.get("comment", "")),
                )
                loaded += 1
        return loaded

    # ------------------------------------------------------------------
    def summary(self) -> dict:
        reviews = self.db.query(HumanReview).all()
        reviewers = sorted({r.reviewer_id for r in reviews if r.reviewer_id})
        cases = sorted({r.case_id for r in reviews if r.case_id})
        completed = bool(reviews)

        if not completed:
            return {
                "validation_completed": False,
                "status": "framework ready - no human reviews recorded yet",
                "reviewers": [],
                "cases_reviewed": 0,
                "total_reviews": 0,
                "acceptance_rate": None,
                "next_action_agreement": None,
                "mean_understanding": None,
                "followup_rate": None,
                "inter_reviewer_agreement": None,
                "agreement_statistic": None,
                "recommended_reviewers": 5,
                "recommended_cases": 12,
                "instructions": HUMAN_INSTRUCTIONS,
            }

        n = len(reviews)
        accepts = sum(1 for r in reviews if r.decision == "ACCEPT")
        agrees = sum(1 for r in reviews if r.action_agrees)
        understandings = [r.understanding for r in reviews if r.understanding]
        followups = sum(1 for r in reviews if r.followup_required)

        kappa, statistic = _inter_reviewer_agreement(reviews)
        return {
            "validation_completed": True,
            "status": f"{n} review(s) from {len(reviewers)} reviewer(s) over {len(cases)} case(s)",
            "reviewers": reviewers,
            "cases_reviewed": len(cases),
            "total_reviews": n,
            "acceptance_rate": round(accepts / n, 3),
            "next_action_agreement": round(agrees / n, 3),
            "mean_understanding": round(sum(understandings) / max(len(understandings), 1), 3),
            "followup_rate": round(followups / n, 3),
            "inter_reviewer_agreement": kappa,
            "agreement_statistic": statistic,
            "recommended_reviewers": 5,
            "recommended_cases": 12,
            "instructions": HUMAN_INSTRUCTIONS,
        }


HUMAN_INSTRUCTIONS = (
    "For each case: read the explanation, decide whether it is acceptable as a "
    "customer message (ACCEPT / REJECT / UNCLEAR), tick whether the stated next "
    "action matches the expected action, score how well the message explains the "
    "progress (1-5), note whether you would still have to follow up, and add an "
    "optional comment. Two reviewers are the minimum for Cohen's kappa; three or "
    "more use Fleiss' kappa."
)


# ----------------------------------------------------------------------
# Agreement statistics (plain Python - no extra dependencies)
# ----------------------------------------------------------------------
def _matrix(reviews) -> tuple[list[str], list[str], dict[tuple[str, str], bool]]:
    """Reviewer/case axes plus a (case, reviewer) -> judgement lookup.

    If a reviewer submits more than once for the same case the most recent row
    wins, so a corrected judgement is not averaged with the original.
    """
    reviewers = sorted({r.reviewer_id for r in reviews if r.reviewer_id})
    cases = sorted({r.case_id for r in reviews if r.case_id})
    cells: dict[tuple[str, str], tuple] = {}
    for r in reviews:
        key = (r.case_id, r.reviewer_id)
        stamp = (r.submitted_at or datetime.min, r.id or 0)
        if key not in cells or stamp >= cells[key][0]:
            cells[key] = (stamp, bool(r.action_agrees))
    flat = {key: value for key, (_stamp, value) in cells.items()}
    return reviewers, cases, flat


def _cohens_kappa(reviews) -> float | None:
    reviewers, cases, cells = _matrix(reviews)
    if len(reviewers) != 2:
        return None
    a, b = reviewers
    pairs = []
    for case in cases:
        if (case, a) in cells and (case, b) in cells:
            pairs.append((cells[(case, a)], cells[(case, b)]))
    return _kappa_from_pairs(pairs)


def _fleiss_kappa(reviews) -> float | None:
    reviewers, cases, cells = _matrix(reviews)
    n_reviewers = len(reviewers)
    if n_reviewers < 3:
        return None
    ratings: list[list[bool]] = []
    for case in cases:
        row = [cells[(case, r)] for r in reviewers if (case, r) in cells]
        if len(row) == n_reviewers:
            ratings.append(row)
    if not ratings:
        return None

    n_items = len(ratings)
    n = n_reviewers

    # Marginal category proportions. For a binary item, n_i,True is the number
    # of reviewers who marked item i as agreeing; P_True is the share of all
    # individual judgements that were positive.
    true_counts = [sum(1 for v in row if v) for row in ratings]
    p_true = sum(true_counts) / (n_items * n)
    proportions = [p_true, 1.0 - p_true]
    observed = sum(x * x for x in proportions)

    # Fleiss' P_i uses ORDERED pairs (j != k), so the numerator counts n*(n-1)
    # comparisons, not the n*(n-1)/2 unordered ones.
    p_i_list = []
    for row in ratings:
        agreeing = sum(
            1 for j in range(n) for k in range(n) if j != k and row[j] == row[k]
        )
        p_i_list.append(agreeing / (n * (n - 1)))
    expected = sum(p_i_list) / n_items

    return _resolve_kappa(observed, expected)


def _resolve_kappa(observed: float, expected: float) -> float | None:
    """Finish a kappa calculation, handling the degenerate 0/0 case.

    When expected agreement is exactly 1.0 the statistic is mathematically
    undefined. Rather than reporting a misleading number, perfect observed
    agreement is reported as 1.0 (the usual convention) and anything else as
    None so the caller can say "not computable".
    """
    if abs(1.0 - expected) < 1e-12:
        return 1.0 if abs(1.0 - observed) < 1e-12 else None
    return round((observed - expected) / (1.0 - expected), 3)


def _kappa_from_pairs(pairs: list[tuple[bool, bool]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    first = sum(1 for a, _ in pairs if a) / n
    second = sum(1 for _, b in pairs if b) / n
    expected = first * second + (1 - first) * (1 - second)
    return _resolve_kappa(observed, expected)


def _inter_reviewer_agreement(reviews) -> tuple[float | None, str | None]:
    reviewers = {r.reviewer_id for r in reviews}
    if len(reviewers) < 2:
        return None, None
    if len(reviewers) == 2:
        return _cohens_kappa(reviews), "cohens_kappa"
    return _fleiss_kappa(reviews), "fleiss_kappa"

