from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException, Query, Request
from fastapi.routing import APIRouter
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..config import settings
from ..database import get_db
from ..engines import ProgressResult
from ..integrations import describe_stub, fetch_ticket, fetch_events as stub_fetch_events
from ..models.explanation import GeneratedExplanation
from ..models.ticket import Ticket
from ..schemas.api import (
    EventImport,
    ImportRequest,
    PublishRequest,
    ReviewRequest,
    RollbackRequest,
    TicketCreate,
)
from ..services.explanation_service import ExplanationService, reference_now
from ..services.evaluation_service import EvaluationService
from ..services.ingestion import normalize_rows_to_orm

router = APIRouter()


def _role(request: Request) -> str:
    return request.headers.get("X-Role", "CUSTOMER").upper() or "CUSTOMER"


def _actor(request: Request) -> str:
    return request.headers.get("X-Actor", "anonymous") or "anonymous"


def _as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid as_of date format")


def _ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail=f"ticket {ticket_id} not found")
    return t


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ticket-progress-explanation-generator",
        "rules_version": settings.rules_version,
        "model_version": settings.model_version,
        "reference_date": settings.reference_date,
        "integration": settings.ticketing_integration,
    }


# ------------------------------------------------------------------ tickets
@router.get("/tickets")
def list_tickets(
    region: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    team: str | None = None,
    risk: str | None = None,
    vendor: str | None = None,
    search: str | None = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Ticket)
    if region:
        q = q.filter(Ticket.region == region)
    if status:
        q = q.filter(Ticket.current_status == status)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if team:
        q = q.filter(Ticket.current_team == team)
    if search:
        q = q.filter(Ticket.ticket_id.ilike(f"%{search}%"))
    total = q.count()
    tickets = q.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()
    svc = ExplanationService(db)
    items = []
    for t in tickets:
        item = t.to_dict()
        try:
            prog = svc.progress(t.ticket_id)
            item["progress_state"] = prog.progress_state
            item["date_status"] = prog.date_status
            item["risk"] = prog.risk
            item["days_remaining"] = prog.days_remaining
            blob = svc.latest_explanation(t.ticket_id, baseline=False)
            item["grounding_score"] = blob.grounding_score if blob else None
        except Exception:
            item["progress_state"] = None
            item["date_status"] = None
            item["risk"] = None
            item["grounding_score"] = None
        items.append(item)
    return {"total": total, "items": items}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    t = _ticket_or_404(db, ticket_id)
    return t.to_dict()


@router.get("/tickets/{ticket_id}/events")
def ticket_events(ticket_id: str, db: Session = Depends(get_db)):
    _ticket_or_404(db, ticket_id)
    svc = ExplanationService(db)
    return {"ticket_id": ticket_id, "events": [e.model_dump(mode="json") for e in svc.get_events(ticket_id)]}


@router.get("/tickets/{ticket_id}/timeline")
def ticket_timeline(ticket_id: str, db: Session = Depends(get_db)):
    _ticket_or_404(db, ticket_id)
    svc = ExplanationService(db)
    tl = svc.timeline(ticket_id)
    return tl.model_dump(mode="json")


@router.get("/tickets/{ticket_id}/progress")
def ticket_progress(ticket_id: str, as_of: str | None = None, db: Session = Depends(get_db)):
    _ticket_or_404(db, ticket_id)
    svc = ExplanationService(db)
    prog = svc.progress(ticket_id, _as_of(as_of))
    return _progress_dict(prog)


@router.get("/tickets/{ticket_id}/dependencies")
def ticket_dependencies(ticket_id: str, db: Session = Depends(get_db)):
    _ticket_or_404(db, ticket_id)
    svc = ExplanationService(db)
    deps = svc.dependencies(ticket_id)
    return {"ticket_id": ticket_id, "dependencies": svc.dependency_engine.chain(deps)}


@router.get("/tickets/{ticket_id}/explanation")
def ticket_explanation(
    ticket_id: str,
    baseline: bool = False,
    version: int | None = None,
    db: Session = Depends(get_db),
):
    _ticket_or_404(db, ticket_id)
    svc = ExplanationService(db)
    if version:
        exp = db.query(GeneratedExplanation).filter(
            GeneratedExplanation.ticket_id == ticket_id,
            GeneratedExplanation.version == version,
            GeneratedExplanation.is_baseline == baseline,
        ).first()
    else:
        exp = svc.latest_explanation(ticket_id, baseline=baseline or None)
    if exp is None:
        raise HTTPException(status_code=404, detail="no explanation generated yet")
    return svc.explanation_with_evidence(exp)


@router.get("/tickets/{ticket_id}/explanation/versions")
def explanation_versions(ticket_id: str, db: Session = Depends(get_db)):
    _ticket_or_404(db, ticket_id)
    rows = (
        db.query(GeneratedExplanation)
        .filter(GeneratedExplanation.ticket_id == ticket_id)
        .order_by(GeneratedExplanation.version.desc())
        .all()
    )
    return {
        "versions": [
            {
                "id": r.id,
                "version": r.version,
                "status": r.status,
                "is_baseline": r.is_baseline,
                "generated_at": r.generated_at.isoformat(),
                "state": r.current_state,
                "score": r.grounding_score,
                "source_version": r.source_version,
            }
            for r in rows
        ]
    }


@router.post("/tickets/{ticket_id}/generate-explanation")
def generate_explanation(
    ticket_id: str,
    generator: str = "rule_based",
    as_of: str | None = None,
    persist: bool = True,
    request: Request = None,
    db: Session = Depends(get_db),
):
    _ticket_or_404(db, ticket_id)
    svc = ExplanationService(db)
    try:
        payload, exp_id = svc.generate(
            ticket_id,
            generator_name=generator,
            as_of=_as_of(as_of),
            actor=_actor(request),
            role=_role(request),
            persist=persist,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = payload.to_api()
    data["explanation_id"] = exp_id
    return data


@router.post("/tickets/{ticket_id}/explanation/review")
def review_explanation(
    ticket_id: str,
    body: ReviewRequest,
    request: Request = None,
    db: Session = Depends(get_db),
):
    _ticket_or_404(db, ticket_id)
    if body.role not in ("REVIEWER", "ADMIN"):
        raise HTTPException(status_code=403, detail="review requires REVIEWER or ADMIN role")
    exp = db.query(GeneratedExplanation).filter(
        GeneratedExplanation.ticket_id == ticket_id,
        GeneratedExplanation.is_baseline == False,  # noqa: E712
    ).order_by(GeneratedExplanation.version.desc()).first()
    if exp is None:
        raise HTTPException(status_code=404, detail="no draft explanation to review")
    if exp.status not in ("DRAFT", "PENDING_REVIEW", "APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail=f"explanation status {exp.status} cannot be reviewed")
    decision = body.decision.upper()
    if decision == "APPROVE":
        new_status = "PENDING_REVIEW" if exp.status == "DRAFT" else "APPROVED"
    elif decision == "REJECT":
        new_status = "REJECTED"
    else:
        raise HTTPException(status_code=400, detail="decision must be APPROVE or REJECT")
    old = exp.status
    exp.status = new_status
    exp.reviewed_by = body.actor
    exp.reviewed_at = datetime.now()
    log_audit(
        db,
        actor=body.actor,
        role=body.role,
        action="EXPLANATION_APPROVED" if new_status in ("APPROVED", "PENDING_REVIEW") else "EXPLANATION_REJECTED",
        ticket_id=ticket_id,
        old_value=old,
        new_value=new_status,
        reason=body.reason,
        source="api",
    )
    db.commit()
    return {"explanation_id": exp.id, "status": exp.status}


@router.post("/tickets/{ticket_id}/explanation/publish")
def publish_explanation(
    ticket_id: str,
    body: PublishRequest,
    request: Request = None,
    db: Session = Depends(get_db),
):
    _ticket_or_404(db, ticket_id)
    if body.role not in ("REVIEWER", "ADMIN"):
        raise HTTPException(status_code=403, detail="publishing requires REVIEWER or ADMIN role")
    exp = db.query(GeneratedExplanation).filter(
        GeneratedExplanation.ticket_id == ticket_id,
        GeneratedExplanation.is_baseline == False,  # noqa: E712
    ).order_by(GeneratedExplanation.version.desc()).first()
    if exp is None:
        raise HTTPException(status_code=404, detail="no explanation to publish")
    if exp.status != "APPROVED":
        raise HTTPException(status_code=400, detail=f"explanation must be APPROVED before publishing (current: {exp.status})")
    exp.status = "PUBLISHED"
    exp.published_at = datetime.now()
    log_audit(
        db,
        actor=body.actor,
        role=body.role,
        action="EXPLANATION_PUBLISHED",
        ticket_id=ticket_id,
        old_value="APPROVED",
        new_value="PUBLISHED",
        reason="high-impact action: customer-facing publication requires approval",
        source="api",
    )
    db.commit()
    svc = ExplanationService(db)
    return svc.explanation_with_evidence(exp)


@router.post("/tickets/{ticket_id}/explanation/rollback")
def rollback_explanation(
    ticket_id: str,
    body: RollbackRequest,
    request: Request = None,
    db: Session = Depends(get_db),
):
    _ticket_or_404(db, ticket_id)
    if body.role != "ADMIN":
        raise HTTPException(status_code=403, detail="rollback requires ADMIN role")
    latest = db.query(GeneratedExplanation).filter(
        GeneratedExplanation.ticket_id == ticket_id,
        GeneratedExplanation.is_baseline == False,  # noqa: E712
    ).order_by(GeneratedExplanation.version.desc()).first()
    if latest is None:
        raise HTTPException(status_code=404, detail="no explanation to roll back")
    if latest.status != "PUBLISHED":
        raise HTTPException(status_code=400, detail="only a PUBLISHED explanation can be rolled back")

    target = None
    target_q = db.query(GeneratedExplanation).filter(GeneratedExplanation.ticket_id == ticket_id)
    if body.target_version:
        target = target_q.filter(GeneratedExplanation.version == body.target_version).first()
    else:
        target = (
            target_q.filter(
                GeneratedExplanation.version < latest.version,
                GeneratedExplanation.is_baseline == False,  # noqa: E712
            )
            .order_by(GeneratedExplanation.version.desc())
            .first()
        )
    if target is None:
        raise HTTPException(status_code=400, detail=f"no older version to roll back to (currently v{latest.version})")

    version_used = latest.version + 1
    rec = GeneratedExplanation(
        ticket_id=ticket_id,
        generated_at=datetime.now(),
        current_state=target.current_state,
        status="PUBLISHED",
        version=version_used,
        explanation=target.explanation,
        grounding_score=target.grounding_score,
        date_status=target.date_status,
        risk=target.risk,
        next_action=target.next_action,
        promised_date=target.promised_date,
        insufficient_evidence=target.insufficient_evidence,
        model_version=target.model_version,
        rules_version=target.rules_version,
        is_baseline=False,
        source_version=target.version,
        published_at=datetime.now(),
    )
    db.add(rec)
    db.flush()
    from ..models.explanation import ExplanationEvidence

    for ev in db.query(ExplanationEvidence).filter(ExplanationEvidence.explanation_id == target.id).all():
        db.add(
            ExplanationEvidence(
                explanation_id=rec.id,
                event_id=ev.event_id,
                reason=ev.reason,
                position=ev.position,
            )
        )
    log_audit(
        db,
        actor=body.actor,
        role=body.role,
        action="ROLLBACK_EXECUTED",
        ticket_id=ticket_id,
        old_value=f"v{latest.version} (bad)",
        new_value=f"v{version_used} restored content of v{target.version}",
        reason=body.reason,
        source="api",
    )
    db.commit()
    return {"rolled_back_to_version": target.version, "new_version": version_used}


@router.get("/tickets/{ticket_id}/audit")
def ticket_audit(ticket_id: str, db: Session = Depends(get_db)):
    _ticket_or_404(db, ticket_id)
    from ..models.audit import AuditLog

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.ticket_id == ticket_id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
    return {"ticket_id": ticket_id, "audit": [r.to_dict() for r in rows]}


# ------------------------------------------------------------------ events
@router.post("/events")
def create_event(body: EventImport, request: Request = None, db: Session = Depends(get_db)):
    from ..services.validation import validate_event

    raw = body.model_dump()
    # ticket must exist
    if not db.query(Ticket).filter(Ticket.ticket_id == raw["ticket_id"]).first():
        raise HTTPException(status_code=404, detail=f"ticket {raw['ticket_id']} not found")
    norm, issues = validate_event(raw, reference_date=settings.reference_date_obj)
    if any(i.level == "error" for i in issues):
        raise HTTPException(status_code=422, detail=[i.to_dict() for i in issues])
    objects, errors = normalize_rows_to_orm([norm], db)
    if not objects:
        raise HTTPException(status_code=409, detail="event already exists or is invalid")
    db.add(objects[0])
    log_audit(
        db,
        actor=_actor(request),
        role=_role(request),
        action="EVENT_IMPORTED",
        ticket_id=raw["ticket_id"],
        new_value=f"event_id={raw['event_id']}, type={raw['event_type']}",
        reason="single event ingest",
        source="api",
    )
    db.commit()
    return {"message": "event imported", "event": objects[0].to_dict()}


@router.post("/tickets/import")
def import_tickets(body: ImportRequest, request: Request = None, db: Session = Depends(get_db)):
    imported_tickets = 0
    imported_events = 0
    issues = []
    for row in body.tickets:
        t = db.query(Ticket).filter(Ticket.ticket_id == row.get("ticket_id")).first()
        if t:
            issues.append(f"ticket {row.get('ticket_id')} skipped (already exists)")
            continue
        try:
            t = Ticket(
                ticket_id=row["ticket_id"],
                customer_reference=row.get("customer_reference", "REF-" + row["ticket_id"]),
                subject=row.get("subject", row["ticket_id"]),
                category=row.get("category", "General"),
                priority=row.get("priority", "P3"),
                region=row.get("region", ""),
                current_team=row.get("current_team", ""),
                current_status=row.get("current_status", "OPEN"),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row.get("updated_at", row["created_at"])),
                promised_date=datetime.fromisoformat(row["promised_date"]) if row.get("promised_date") else None,
                actual_resolution_date=datetime.fromisoformat(row["actual_resolution_date"]) if row.get("actual_resolution_date") else None,
                sla_status=row.get("sla_status", "ACTIVE"),
            )
            db.add(t)
            imported_tickets += 1
        except KeyError as e:
            issues.append(f"ticket row missing field: {e}")
        except ValueError as e:
            issues.append(f"ticket {row.get('ticket_id')} bad date: {e}")
    db.flush()

    raw_events = [e.model_dump() for e in body.events]
    objects, errors = normalize_rows_to_orm(raw_events, db)
    for obj in objects:
        db.add(obj)
        imported_events += 1
    issues.extend(errors)

    log_audit(
        db,
        actor=_actor(request),
        role=_role(request),
        action="EVENT_IMPORTED",
        new_value=f"tickets={imported_tickets}, events={imported_events}",
        reason=f"bulk import from {body.source}",
        source="api",
    )
    db.commit()
    return {"tickets_imported": imported_tickets, "events_imported": imported_events, "issues": issues[:50]}


# ------------------------------------------------------------------ evaluation
@router.get("/evaluation/summary")
def evaluation_summary(db: Session = Depends(get_db)):
    from ..models.evaluation import ExperimentRun

    run = db.query(ExperimentRun).order_by(ExperimentRun.id.desc()).first()
    if run is None:
        return {"has_run": False, "message": "no evaluation run yet"}
    data = run.to_dict()
    data["has_run"] = True
    return data


@router.get("/evaluation/results")
def evaluation_results(db: Session = Depends(get_db)):
    from ..models.evaluation import EvaluationResult

    rows = db.query(EvaluationResult).order_by(EvaluationResult.id.desc()).all()
    return {"results": [r.to_dict() for r in rows]}


@router.post("/evaluation/run")
def run_evaluation(request: Request = None, db: Session = Depends(get_db)):
    svc = EvaluationService(db)
    try:
        result = svc.run()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/evaluation/human")
def submit_human_evaluation(
    payload: dict,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Store a human reviewer result for a case (separate from synthetic runs)."""
    from ..models.evaluation import EvaluationResult

    case_id = payload.get("case_id")
    rec = db.query(EvaluationResult).filter(EvaluationResult.case_id == case_id).order_by(
        EvaluationResult.id.desc()
    ).first()
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no evaluation row for case {case_id}")
    rec.human_understanding = float(payload["understanding"])
    rec.human_followup = bool(payload.get("followup"))
    log_audit(
        db,
        actor=_actor(request),
        role="REVIEWER",
        action="EXPLANATION_REVIEWED",
        ticket_id=rec.ticket_id,
        new_value=f"human_understanding={rec.human_understanding}, followup={rec.human_followup}",
        reason="human validation submitted for case " + case_id,
        source="api",
    )
    db.commit()
    return {"message": "human result stored", "case_id": case_id}


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard/metrics")
def dashboard_metrics(db: Session = Depends(get_db)):
    from ..models.evaluation import ExperimentRun, EvaluationResult

    total = db.query(func.count(Ticket.ticket_id)).scalar() or 0
    svc = ExplanationService(db)
    tickets = db.query(Ticket).all()
    states = {"TOTAL": total}
    counts = {}
    for t in tickets:
        try:
            prog = svc.progress(t.ticket_id)
            counts["state_" + prog.progress_state] = counts.get("state_" + prog.progress_state, 0) + 1
        except Exception:
            pass
    region_counts = {}
    for t in tickets:
        region_counts[t.region] = region_counts.get(t.region, 0) + 1
    priority_counts = {}
    for t in tickets:
        priority_counts[t.priority] = priority_counts.get(t.priority, 0) + 1
    status_counts = {}
    for t in tickets:
        status_counts[t.current_status] = status_counts.get(t.current_status, 0) + 1

    run = db.query(ExperimentRun).order_by(ExperimentRun.id.desc()).first()
    metrics = run.to_dict() if run else None

    grounding_scores = (
        db.query(func.avg(GeneratedExplanation.grounding_score))
        .filter(GeneratedExplanation.is_baseline == False)  # noqa: E712
        .scalar()
    )

    return {
        "totals": {
            "tickets": total,
            "resolved": counts.get("state_RESOLVED", 0),
            "blocked": counts.get("state_BLOCKED", 0),
            "waiting_approval": counts.get("state_WAITING_FOR_APPROVAL", 0),
            "waiting_vendor": counts.get("state_WAITING_FOR_VENDOR", 0),
            "waiting_customer": counts.get("state_WAITING_FOR_CUSTOMER", 0),
            "delayed": counts.get("state_DELAYED", 0),
            "in_progress": counts.get("state_IN_PROGRESS", 0) + counts.get("state_INVESTIGATING", 0),
        },
        "states": counts,
        "status": status_counts,
        "regions": region_counts,
        "priorities": priority_counts,
        "evaluation": metrics,
        "avg_grounding_score": round(float(grounding_scores or 0), 1),
    }


# ------------------------------------------------------------------ integration stub
@router.get("/integrations/stub")
def integration_stub_info():
    return describe_stub()


@router.get("/integrations/stub/ticket/{ticket_id}")
def integration_stub_ticket(ticket_id: str):
    row = fetch_ticket(ticket_id)
    if "error" in row:
        raise HTTPException(status_code=404, detail=row["error"])
    return row


@router.get("/integrations/stub/events/{ticket_id}")
def integration_stub_events(ticket_id: str):
    events = stub_fetch_events(ticket_id)
    return {"count": len(events), "events": events}


def _progress_dict(p: ProgressResult) -> dict:
    return {
        "ticket_id": p.ticket_id,
        "progress_state": p.progress_state,
        "effective_status": p.effective_status,
        "date_status": p.date_status,
        "risk": p.risk,
        "days_remaining": p.days_remaining,
        "overdue_days": p.overdue_days,
        "promised_date": p.promised_date.isoformat() if p.promised_date else None,
        "next_action": p.next_action,
        "next_action_evidence": p.next_action_evidence,
        "reasons": p.reasons,
        "blockers": p.blockers,
        "waiting_on": p.waiting_on,
        "evidence_event_ids": p.evidence_ids,
    }