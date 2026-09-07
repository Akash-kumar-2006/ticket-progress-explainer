"""Dataset validation.

Runs the data-quality rules from backend/app/services/validation.py over the
raw synthetic data and writes a JSON report to data/processed/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.app.constants import EVENT_TYPES, TICKET_STATUSES
from backend.app.services.validation import validate_event, validate_ticket_row, parse_timestamp

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"


def run() -> dict:
    tickets_df = pd.read_csv(RAW / "tickets.csv")
    events_df = pd.read_csv(RAW / "events.csv")

    ticket_issues = []
    for _, row in tickets_df.iterrows():
        for issue in validate_ticket_row(row.to_dict()):
            ticket_issues.append({**issue.to_dict(), "ticket_id": row.get("ticket_id")})

    event_issues = []
    seen_ids: dict[str, int] = {}
    prior_max: dict[str, object] = {}

    for _, row in events_df.iterrows():
        d = row.to_dict()
        eid = str(d.get("event_id", ""))
        seen_ids[eid] = seen_ids.get(eid, 0) + 1
        ts = parse_timestamp(d.get("timestamp"))
        ticket_id = str(d.get("ticket_id", ""))
        prior = prior_max.get(ticket_id)
        norm, issues = validate_event(
            d, prior_max_ts=prior, reference_date=_reference_date()
        )
        for issue in issues:
            event_issues.append(issue.to_dict())
        if prior is not None and ts is not None and ts < prior:
            pass  # already reported by validate_event
        else:
            prior_max[ticket_id] = ts or prior

    duplicate_ids = [k for k, v in seen_ids.items() if v > 1]

    summary = {
        "tickets_checked": int(len(tickets_df)),
        "events_checked": int(len(events_df)),
        "ticket_issues": len(ticket_issues),
        "event_issues": len(event_issues),
        "duplicate_event_ids": duplicate_ids,
        "invalid_event_types": sorted({i.get("event_id") for i in event_issues if i.get("field") == "event_type"}),
    }
    report = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "summary": summary,
        "rules": {
            "missing_ticket_id": "error",
            "missing_timestamp": "error",
            "invalid_event_type": "error",
            "duplicate_event_id": "error",
            "future_timestamp": "error",
            "impossible_status_transition": "error",
            "malformed_date": "error",
            "inconsistent_promised_date": "warning",
            "out_of_order": "warning",
        },
        "ticket_issues": ticket_issues[:100],
        "event_issues": event_issues[:200],
        "note": "Deliberate edge cases (conflicts, duplicates, out-of-order) are expected; "
                "the pipeline tolerates and flags them.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "validation_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print("validation report ->", OUT / "validation_report.json")
    return report


def _reference_date():
    from backend.app.config import settings

    return settings.reference_date_obj


if __name__ == "__main__":
    run()