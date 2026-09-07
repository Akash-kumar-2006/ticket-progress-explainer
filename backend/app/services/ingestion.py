"""Ingestion: raw event dicts -> normalized EventData for the engine layer."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..engines.models import EventData
from ..models.event import TicketEvent

STATUS_SETTED = {"STATUS_CHANGE", "RESOLUTION", "REOPENED"}


def _to_str(v, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, float) and v != v:  # NaN
        return default
    s = str(v)
    return default if s.strip().lower() in ("", "nan") else s


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    s = str(v)
    return None if s.strip().lower() in ("", "nan") else s


def event_to_data(e: TicketEvent) -> EventData:
    return EventData(
        event_id=e.event_id,
        ticket_id=e.ticket_id,
        timestamp=e.timestamp,
        event_type=e.event_type,
        actor_type=e.actor_type,
        actor_id=e.actor_id,
        region=e.region,
        team=e.team,
        old_status=e.old_status,
        new_status=e.new_status,
        message=e.message,
        dependency_id=e.dependency_id,
        dependency_title=e.dependency_title,
        dependency_owner=e.dependency_owner,
        vendor=e.vendor,
        vendor_item=e.vendor_item,
        approval_type=e.approval_type,
        promised_date=e.promised_date,
        is_duplicate=e.is_duplicate,
        is_out_of_order=e.is_out_of_order,
        conflict_flag=e.conflict_flag,
        metadata=json.loads(e.metadata_json or "{}"),
    )


def normalize_rows_to_orm(rows: list[dict], db: Session) -> tuple[list[TicketEvent], list[str]]:
    """Normalize a batch of raw event dicts and build (unsaved) ORM objects.

    Detects duplicates (by event_id across the batch + existing DB) and
    out-of-order arrivals per ticket. Returns (objects, errors).
    """
    errors: list[str] = []
    objects: list[TicketEvent] = []
    existing_ids = set()
    if db:
        rows_snapshot = db.query(TicketEvent.event_id).all()
        existing_ids = {r[0] for r in rows_snapshot}

    seen_ticket_max: dict[str, datetime] = {}
    seen_ids_within_batch: set[str] = set()
    conflict_info = _status_conflicts_for(rows)

    for raw in rows:
        eid = str(raw.get("event_id", ""))
        if not eid:
            errors.append("row missing event_id")
            continue
        if eid in existing_ids or eid in seen_ids_within_batch:
            errors.append(f"duplicate event_id {eid}")
            continue
        seen_ids_within_batch.add(eid)

        ts = raw.get("timestamp")
        try:
            ts_dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
        except (TypeError, ValueError):
            errors.append(f"event {eid}: bad timestamp")
            continue

        ticket_id = str(raw.get("ticket_id", ""))
        is_ooo = False
        prior = seen_ticket_max.get(ticket_id)
        if prior is not None and ts_dt < prior:
            is_ooo = True
        if prior is None or ts_dt > prior:
            seen_ticket_max[ticket_id] = ts_dt

        meta = raw.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (ValueError, TypeError):
                meta = {}
                errors.append(f"event {eid}: bad metadata json")
        if not isinstance(meta, dict):
            meta = {}

        obj = TicketEvent(
            event_id=eid,
            ticket_id=ticket_id,
            timestamp=ts_dt,
            event_type=_to_str(raw.get("event_type")),
            actor_type=_to_str(raw.get("actor_type"), "AGENT"),
            actor_id=_to_str(raw.get("actor_id")),
            region=_to_str(raw.get("region")),
            team=_to_str(raw.get("team")),
            old_status=_clean(raw.get("old_status")),
            new_status=_clean(raw.get("new_status")),
            message=_to_str(raw.get("message")),
            dependency_id=_clean(raw.get("dependency_id")),
            dependency_title=_clean(raw.get("dependency_title")),
            dependency_owner=_clean(raw.get("dependency_owner")),
            vendor=_clean(raw.get("vendor")),
            vendor_item=_clean(raw.get("vendor_item")),
            approval_type=_clean(raw.get("approval_type")),
            metadata_json=json.dumps(meta, default=str),
        )
        obj.promised_date = _clean(raw.get("promised_date"))
        if isinstance(obj.promised_date, str):
            obj.promised_date = datetime.fromisoformat(obj.promised_date)
        obj.is_duplicate = False
        obj.is_out_of_order = is_ooo
        obj.conflict_flag = eid in conflict_info
        objects.append(obj)
    return objects, errors


def _status_conflicts_for(rows: list[dict]) -> set[str]:
    """Flag events that contradict an earlier RESOLVED status."""
    flagged: set[str] = set()
    by_ticket: dict[str, list] = {}
    for raw in rows:
        if raw.get("event_type") in STATUS_SETTED and raw.get("new_status"):
            by_ticket.setdefault(str(raw.get("ticket_id")), []).append(raw)
    for _, evs in by_ticket.items():
        evs.sort(key=lambda r: r.get("timestamp", ""))
        prev_status = None
        for e in evs:
            ns = e.get("new_status")
            if prev_status == "RESOLVED" and ns in ("OPEN", "IN_PROGRESS", "PENDING", "ESCALATED", "REOPENED"):
                flagged.add(str(e.get("event_id")))
            if ns:
                prev_status = ns
    return flagged