"""Mock integration with a ServiceNow/Jira-like ticketing system.

Every function returns realistic-but-synthetic responses so the pipeline can be
demonstrated and developed with zero external credentials. To connect a real
ticketing system later, replace the body of each function with an HTTP call to
the vendor REST API and keep the return contracts identical.

Contracts:
  fetch_ticket(ticket_id) -> dict       ticket fields
  fetch_events(ticket_id) -> list[dict] chronological raw events
  fetch_work_notes(...)                 subset of events
  fetch_approvals(...)                  approval records
  fetch_vendor_updates(...)             vendor update records
  fetch_promised_dates(...)             promised date records
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import PROJECT_ROOT

STUB_SYSTEM = "ServiceNow-stub"


def _now() -> datetime:
    return datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _load_raw(ticket_id: str) -> list[dict]:
    """Reads from the local synthetic event store via the database layer.

    The functions below are isolated here so a real backend could reuse them.
    """
    import json

    import pandas as pd

    events_csv = PROJECT_ROOT / "data" / "raw" / "events.csv"
    try:
        df = pd.read_csv(events_csv)
    except FileNotFoundError:
        return []
    col = df.columns.tolist()
    if "ticket_id" not in col:
        return []

    def row_to_dict(r) -> dict:
        out = {c: (("" if pd.isna(v) else v) if isinstance(v, (float)) else v) for c, v in r.items()}
        for c in ("old_status", "new_status", "dependency_id", "vendor", "approval_type", "promised_date"):
            if c in out and out[c] in (None, "", float("nan")):
                out[c] = None
        out["metadata"] = json.loads(out.get("metadata") or "{}")
        return out

    subset = df[df["ticket_id"] == ticket_id].sort_values("timestamp")
    return [row_to_dict(r) for r in subset.to_dict(orient="records")]


def fetch_ticket(ticket_id: str) -> dict:
    """Return a synthetic ticket record. Mirrors a GET of a ticket."""
    import pandas as pd

    try:
        df = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "tickets.csv")
    except FileNotFoundError:
        return {"ticket_id": ticket_id, "error": "ticket store not found"}
    row = df[df["ticket_id"] == ticket_id]
    if row.empty:
        return {"ticket_id": ticket_id, "error": "ticket not found in stub"}
    return {c: (None if (isinstance(v, float) and pd.isna(v)) else v)
            for c, v in row.iloc[0].items()}


def fetch_events(ticket_id: str) -> list[dict]:
    return _load_raw(ticket_id)


def fetch_work_notes(ticket_id: str) -> list[dict]:
    return [e for e in _load_raw(ticket_id) if e["event_type"] == "WORK_NOTE"]


def fetch_approvals(ticket_id: str) -> list[dict]:
    return [e for e in _load_raw(ticket_id) if "APPROVAL" in e["event_type"]]


def fetch_vendor_updates(ticket_id: str) -> list[dict]:
    return [e for e in _load_raw(ticket_id) if e["event_type"] == "VENDOR_UPDATE"]


def fetch_promised_dates(ticket_id: str) -> list[dict]:
    return [e for e in _load_raw(ticket_id) if "PROMISED_DATE" in e["event_type"]]


def describe_stub() -> dict:
    return {
        "integration": STUB_SYSTEM,
        "mode": "offline mock — no external credentials required",
        "replace_with": "implement fetch_* with your ticketing API; keep return contracts identical",
        "capabilities": [
            "fetch_ticket",
            "fetch_events",
            "fetch_work_notes",
            "fetch_approvals",
            "fetch_vendor_updates",
            "fetch_promised_dates",
        ],
        "generated": _iso(_now()),
    }