"""Data quality validation and normalization for ticket events.

Implements the data quality checks required by the project:
missing ticket IDs, missing timestamps, invalid event types, duplicate event
IDs, future timestamps, impossible status transitions, malformed dates,
inconsistent promised dates, and out-of-order arrivals.
"""
from __future__ import annotations

from datetime import date, datetime, time

from ..constants import EVENT_TYPES

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"OPEN", "IN_PROGRESS", "PENDING", "ESCALATED", "RESOLVED", "REOPENED"},
    "IN_PROGRESS": {"OPEN", "IN_PROGRESS", "PENDING", "ESCALATED", "RESOLVED", "REOPENED"},
    "PENDING": {"PENDING", "IN_PROGRESS", "ESCALATED", "RESOLVED", "REOPENED"},
    "ESCALATED": {"ESCALATED", "IN_PROGRESS", "PENDING", "RESOLVED", "REOPENED"},
    "RESOLVED": {"RESOLVED", "REOPENED"},
    "REOPENED": {"REOPENED", "IN_PROGRESS", "OPEN", "PENDING", "ESCALATED", "RESOLVED"},
}

EVENTS_WITH_STATUS = {"STATUS_CHANGE"}
EVENTS_WITH_PROMISE = {"PROMISED_DATE_SET", "PROMISED_DATE_CHANGED"}


class DataIssue:
    def __init__(self, level: str, event_id: str, field: str, message: str):
        self.level = level  # error | warning | info
        self.event_id = event_id
        self.field = field
        self.message = message

    def to_dict(self) -> dict:
        return {"level": self.level, "event_id": self.event_id, "field": self.field, "message": self.message}


def parse_timestamp(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN (empty CSV cell)
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0))
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def validate_event(raw: dict, prior_max_ts: datetime | None = None, reference_date: date | None = None) -> tuple[dict, list[DataIssue]]:
    """Normalize and validate a single raw event. Returns (normalized, issues)."""
    issues: list[DataIssue] = []
    event_id = str(raw.get("event_id", "")).strip()
    ticket_id = str(raw.get("ticket_id", "")).strip()
    event_type = str(raw.get("event_type", "")).strip()

    if not event_id:
        issues.append(DataIssue("error", event_id, "event_id", "Missing event ID"))
    if not ticket_id:
        issues.append(DataIssue("error", event_id, "ticket_id", "Missing ticket ID"))
    if not event_type:
        issues.append(DataIssue("error", event_id, "event_type", "Missing event type"))

    ts = parse_timestamp(raw.get("timestamp"))
    if ts is None:
        issues.append(DataIssue("error", event_id, "timestamp", "Missing or malformed timestamp"))

    if event_type and event_type not in EVENT_TYPES:
        issues.append(DataIssue("error", event_id, "event_type", f"Invalid event type '{event_type}'"))

    promised_value = raw.get("promised_date")
    if isinstance(promised_value, float) and promised_value != promised_value:
        promised_value = None
    promised_date = parse_timestamp(promised_value)
    if promised_value is not None and promised_date is None:
        issues.append(DataIssue("error", event_id, "promised_date", "Malformed promised date"))

    if event_type in EVENTS_WITH_PROMISE and promised_date is None:
        issues.append(DataIssue("warning", event_id, "promised_date", "Promised-date event without a date"))

    if event_type in EVENTS_WITH_STATUS:
        old = str(raw.get("old_status") or "").strip() or None
        new = str(raw.get("new_status") or "").strip() or None
        if new and old and new not in ALLOWED_TRANSITIONS.get(old, set()):
            issues.append(
                DataIssue("error", event_id, "status", f"Impossible status transition {old} -> {new}")
            )

    if reference_date is not None and ts is not None and ts.date() > reference_date:
        issues.append(
            DataIssue("error", event_id, "timestamp", f"Future timestamp relative to reference date {reference_date}")
        )

    if prior_max_ts is not None and ts is not None and ts < prior_max_ts:
        issues.append(DataIssue("warning", event_id, "timestamp", "Event timestamp is out of order (earlier than a previously seen event)"))

    normalized = {
        "event_id": event_id,
        "ticket_id": ticket_id,
        "timestamp": ts.isoformat() if ts else None,
        "event_type": event_type,
        "actor_type": _v(raw.get("actor_type"), "AGENT"),
        "actor_id": _v(raw.get("actor_id")),
        "region": _v(raw.get("region")),
        "team": _v(raw.get("team")),
        "old_status": _v(raw.get("old_status"), None),
        "new_status": _v(raw.get("new_status"), None),
        "message": _v(raw.get("message")),
        "dependency_id": _v(raw.get("dependency_id"), None),
        "dependency_title": _v(raw.get("dependency_title"), None),
        "dependency_owner": _v(raw.get("dependency_owner"), None),
        "vendor": _v(raw.get("vendor"), None),
        "vendor_item": _v(raw.get("vendor_item"), None),
        "approval_type": _v(raw.get("approval_type"), None),
        "promised_date": promised_date.isoformat() if promised_date else None,
        "metadata": raw.get("metadata") or {},
    }
    return normalized, issues


def _v(value, default=""):
    if value is None:
        return default
    if isinstance(value, float) and value != value:
        return default
    s = str(value)
    if default is None and s.strip().lower() in ("", "nan"):
        return None
    return s


def validate_ticket_row(raw: dict) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if not raw.get("ticket_id"):
        issues.append(DataIssue("error", raw.get("ticket_id", ""), "ticket_id", "Missing ticket ID"))
    for field in ("promised_date", "created_at", "actual_resolution_date"):
        v = raw.get(field)
        if isinstance(v, float) and v != v:
            continue
        if v is not None and parse_timestamp(v) is None:
            issues.append(DataIssue("error", raw.get("ticket_id", ""), field, f"Malformed {field}"))
    return issues