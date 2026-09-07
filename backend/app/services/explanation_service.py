"""Orchestration service: ties engines, generators, persistence and audit together."""
from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session

from ..config import settings
from ..engines import (
    DependencyEngine,
    EvidenceSelector,
    ProgressStateEngine,
    TimelineEngine,
    compute_grounding,
    DateAnalysis,
)
from ..engines.models import (
    DependencyInfo,
    EventData,
    ExplanationPayload,
    ProgressResult,
)
from ..generators import get_generator
from ..models.event import TicketEvent
from ..models.explanation import ExplanationEvidence, GeneratedExplanation
from ..models.ticket import Ticket
from ..audit import log_audit
from .ingestion import event_to_data

DEFAULT_REFERENCE_TIME = time(12, 0)


def reference_now() -> datetime:
    return datetime.combine(settings.reference_date_obj, DEFAULT_REFERENCE_TIME)


class ExplanationService:
    def __init__(self, db: Session):
        self.db = db
        self.timeline_engine = TimelineEngine()
        self.dependency_engine = DependencyEngine()
        self.state_engine = ProgressStateEngine()
        self.evidence_selector = EvidenceSelector()

    # ------------------------------------------------------------- loaders
    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self.db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()

    def get_events(self, ticket_id: str) -> list[EventData]:
        rows = (
            self.db.query(TicketEvent)
            .filter(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.timestamp)
            .all()
        )
        return [event_to_data(r) for r in rows]

    def ticket_dict(self, ticket: Ticket) -> dict:
        return ticket.to_dict()

    # ------------------------------------------------------- engine facade
    def timeline(self, ticket_id: str):
        ticket = self.get_ticket(ticket_id)
        events = self.get_events(ticket_id)
        created = ticket.created_at if ticket else None
        tl = self.timeline_engine.build(events, created)
        return tl

    def dependencies(self, ticket_id: str) -> list[DependencyInfo]:
        events = self.get_events(ticket_id)
        return self.dependency_engine.build(events)

    def progress(self, ticket_id: str, as_of: datetime | None = None) -> ProgressResult:
        ticket = self.get_ticket(ticket_id)
        events = self.get_events(ticket_id)
        deps = self.dependency_engine.build(events)
        now = as_of or reference_now()
        return self.state_engine.analyze(
            ticket_id=ticket_id,
            ticket_status=ticket.current_status if ticket else None,
            promised_date=ticket.promised_date if ticket else None,
            events=events,
            deps=deps,
            now=now,
        )

    def _evidence_and_grounding(self, progress: ProgressResult, events: list[EventData], deps, now):
        evidence = self.evidence_selector.select(events, progress)
        date_info = DateAnalysis(
            date_status=progress.date_status,
            risk=progress.risk,
            days_remaining=progress.days_remaining,
            overdue_days=progress.overdue_days,
        )
        score, breakdown = compute_grounding(evidence, events, deps, date_info, now)
        return evidence, score, breakdown

    # -------------------------------------------------------- generation
    def generate(
        self,
        ticket_id: str,
        generator_name: str = "rule_based",
        as_of: datetime | None = None,
        actor: str = "system",
        role: str = "SYSTEM",
        persist: bool = True,
    ) -> tuple[ExplanationPayload, int | None]:
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise KeyError(f"ticket {ticket_id} not found")
        events = self.get_events(ticket_id)
        deps = self.dependency_engine.build(events)
        now = as_of or reference_now()
        progress = self.state_engine.analyze(
            ticket_id=ticket_id,
            ticket_status=ticket.current_status,
            promised_date=ticket.promised_date,
            events=events,
            deps=deps,
            now=now,
        )
        evidence, score, breakdown = self._evidence_and_grounding(progress, events, deps, now)
        gen = get_generator(generator_name)
        payload = gen.generate(
            ticket=ticket.to_dict(),
            events=events,
            progress=progress,
            evidence=evidence,
            deps=deps,
            now=now,
            grounding_score=score,
            grounding_breakdown=breakdown,
            model_version=settings.model_version if not payload_is_baseline(gen.name) else "baseline-1.0.0",
            rules_version=settings.rules_version,
        )
        payload.model_version = settings.model_version if gen.name != "baseline" else "baseline-1.0.0"

        explanation_id = None
        if persist:
            explanation_id = self._persist(payload, actor, role, is_baseline=gen.name == "baseline", generator_name=gen.name)
        return payload, explanation_id

    def _persist(self, payload: ExplanationPayload, actor: str, role: str, is_baseline: bool, generator_name: str = "rule_based") -> int:
        version = self._next_version(payload.ticket_id)
        rec = GeneratedExplanation(
            ticket_id=payload.ticket_id,
            generated_at=datetime.now(),
            current_state=payload.progress_state,
            status="DRAFT",
            version=version,
            explanation=payload.explanation,
            grounding_score=float(payload.grounding_score),
            date_status=payload.date_status,
            risk=payload.risk,
            next_action=payload.next_action,
            promised_date=payload.promised_date,
            insufficient_evidence=payload.insufficient_evidence,
            model_version=payload.model_version,
            rules_version=payload.rules_version,
            is_baseline=is_baseline,
        )
        self.db.add(rec)
        self.db.flush()
        for pos, ev in enumerate(payload.evidence):
            self.db.add(
                ExplanationEvidence(
                    explanation_id=rec.id,
                    event_id=ev.event_id,
                    reason=ev.reason,
                    position=pos,
                )
            )
        log_audit(
            self.db,
            actor=actor,
            role=role,
            action="EXPLANATION_GENERATED",
            ticket_id=payload.ticket_id,
            new_value=f"state={payload.progress_state} score={payload.grounding_score} baseline={is_baseline}",
            reason=f"generated with generator={generator_name}",
            source="service",
        )
        self.db.commit()
        self.db.refresh(rec)
        return rec.id

    def _next_version(self, ticket_id: str) -> int:
        latest = (
            self.db.query(GeneratedExplanation.version)
            .filter(GeneratedExplanation.ticket_id == ticket_id)
            .order_by(GeneratedExplanation.version.desc())
            .first()
        )
        return (latest[0] + 1) if latest else 1

    def latest_explanation(self, ticket_id: str, baseline: bool | None = None) -> GeneratedExplanation | None:
        q = self.db.query(GeneratedExplanation).filter(GeneratedExplanation.ticket_id == ticket_id)
        if baseline is not None:
            q = q.filter(GeneratedExplanation.is_baseline == baseline)
        return q.order_by(GeneratedExplanation.version.desc()).first()

    def explanation_with_evidence(self, exp: GeneratedExplanation) -> dict:
        evs = (
            self.db.query(ExplanationEvidence)
            .filter(ExplanationEvidence.explanation_id == exp.id)
            .order_by(ExplanationEvidence.position)
            .all()
        )
        events = {e.event_id: e for e in self.get_events(exp.ticket_id)}
        evidence_list = [
            {
                "explanation_evidence_id": e.id,
                "event_id": e.event_id,
                "reason": e.reason,
                "event": events[e.event_id].label() if e.event_id in events else None,
            }
            for e in evs
        ]
        return {
            "id": exp.id,
            "ticket_id": exp.ticket_id,
            "generated_at": exp.generated_at.isoformat(),
            "status": exp.status,
            "version": exp.version,
            "current_state": exp.current_state,
            "explanation": exp.explanation,
            "grounding_score": exp.grounding_score,
            "date_status": exp.date_status,
            "risk": exp.risk,
            "next_action": exp.next_action,
            "promised_date": exp.promised_date.isoformat() if exp.promised_date else None,
            "insufficient_evidence": exp.insufficient_evidence,
            "model_version": exp.model_version,
            "rules_version": exp.rules_version,
            "is_baseline": exp.is_baseline,
            "source_version": exp.source_version,
            "reviewed_by": exp.reviewed_by,
            "published_at": exp.published_at.isoformat() if exp.published_at else None,
            "evidence": evidence_list,
            "claims": [],
        }


def payload_is_baseline(name: str) -> bool:
    return name == "baseline"