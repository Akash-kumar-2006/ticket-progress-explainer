"""Baseline generator.

A deliberately naive explanation that uses ONLY the current ticket status.
It performs no event reasoning. It is the comparison baseline reported in the
evaluation experiment.
"""
from ..engines.models import ExplanationPayload, ProgressResult
from .base import ExplanationGenerator

STATUS_EXPLANATIONS = {
    "OPEN": "Your ticket is open and being processed.",
    "IN_PROGRESS": "Your ticket is currently being worked on.",
    "PENDING": "Your ticket is currently pending.",
    "ESCALATED": "Your ticket has been escalated to another team.",
    "RESOLVED": "Your ticket has been resolved.",
    "REOPENED": "Your ticket has been reopened.",
    "CLOSED": "Your ticket has been closed.",
}


class BaselineExplanationGenerator(ExplanationGenerator):
    name = "baseline"

    def generate(
        self,
        *,
        ticket: dict,
        events,
        progress: ProgressResult,
        evidence,
        deps,
        now,
        grounding_score: int,
        grounding_breakdown: list[str],
        model_version: str,
        rules_version: str,
    ) -> ExplanationPayload:
        status = progress.effective_status or ticket.get("current_status", "OPEN")
        text = STATUS_EXPLANATIONS.get(status, "Your ticket is open and being processed.")
        return ExplanationPayload(
            ticket_id=ticket["ticket_id"],
            progress_state=status,
            effective_status=status,
            date_status=None,
            risk="NO_DATE",
            grounding_score=0,
            grounding_breakdown=["Baseline uses status only; no events are examined."],
            explanation=text,
            claims=[],
            evidence=[],
            next_action=None,
            next_action_evidence=[],
            promised_date=None,
            insufficient_evidence=True,
            model_version="baseline-1.0.0",
            rules_version=rules_version,
            is_baseline=True,
        )