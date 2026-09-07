"""Generate data/evaluation/evaluation_cases.csv.

Reference (expected) labels are derived from the synthetic scenario:
the pending dependency kinds, the promised-date rule and terminal events. This
is a deterministic reference used by the synthetic evaluation. Human reviewer
scores are stored separately once collected (see docs/VALIDATION.md).

Columns:
  case_id, ticket_id, expected_state, expected_blocker, expected_next_action,
  expected_date_status, difficulty, failure_case,
  human_understanding_score, human_followup_required, baseline_score, prototype_score
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.app.config import settings
from backend.app.engines import DependencyEngine, ProgressStateEngine
from backend.app.engines.models import EventData
from backend.app.engines.timeline import TimelineEngine
from backend.app.services.explanation_service import reference_now
from backend.app.services.ingestion import _status_conflicts_for

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "evaluation"
EXTRA_CASES = 34  # pick regular tickets until we reach >= REQUIRED total
MIN_CASES = 30


def _load_events() -> dict[str, list[EventData]]:
    df = pd.read_csv(RAW / "events.csv")
    by_ticket: dict[str, list[EventData]] = {}
    for _, row in df.iterrows():
        ts = pd.Timestamp(row["timestamp"]).to_pydatetime()
        ev = EventData(
            event_id=str(row["event_id"]),
            ticket_id=str(row["ticket_id"]),
            timestamp=ts,
            event_type=str(row["event_type"]),
            region=str(row.get("region") or ""),
            team=str(row.get("team") or ""),
            old_status=row.get("old_status") if isinstance(row.get("old_status"), str) else None,
            new_status=row.get("new_status") if isinstance(row.get("new_status"), str) else None,
            message=str(row.get("message") or ""),
            dependency_id=row.get("dependency_id") if isinstance(row.get("dependency_id"), str) else None,
            vendor=row.get("vendor") if isinstance(row.get("vendor"), str) else None,
            approval_type=row.get("approval_type") if isinstance(row.get("approval_type"), str) else None,
        )
        if row.get("promised_date") and isinstance(row["promised_date"], str):
            ev.promised_date = pd.Timestamp(row["promised_date"]).to_pydatetime()
        by_ticket.setdefault(str(row["ticket_id"]), []).append(ev)
    for k in by_ticket:
        by_ticket[k].sort(key=lambda e: (e.timestamp, e.event_id))
    # mark conflicts the same way the store normalizer does
    raw_rows = df.to_dict(orient="records")
    flagged = _status_conflicts_for(raw_rows)
    for ev_list in by_ticket.values():
        for ev in ev_list:
            ev.conflict_flag = ev.event_id in flagged
    return by_ticket


def _failure_case(events: list[EventData], progress_state: str, date_status) -> str:
    types = [e.event_type for e in events]
    tl = TimelineEngine().build(events)
    if progress_state == "REOPENED":
        return "reopened"
    if tl.conflicts:
        return "conflicting_events"
    if tl.duplicates:
        return "duplicate_events"
    if [e for e in events if e.is_out_of_order] or tl.out_of_order:
        return "out_of_order_events"
    if date_status == "OVERDUE":
        return "overdue_promised_date"
    if not events:
        return "missing_evidence"
    if types.count("TEAM_TRANSFER") >= 2:
        return "multiple_regional_transfers"
    return "none"


def _build_cases(events_by_ticket: dict[str, list[EventData]], tickets: pd.DataFrame) -> list[dict]:
    dep_engine = DependencyEngine()
    state_engine = ProgressStateEngine()
    tickets.set_index("ticket_id", inplace=True)

    selected = ["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004", "DEMO-005", "DEMO-006", "DEMO-007",
                "XTCK-001", "XTCK-002"]
    for tid in tickets.index:
        if tid in selected:
            continue
        selected.append(tid)
        if len(selected) >= len(tickets.index) or len(selected) >= MIN_CASES + EXTRA_CASES:
            break

    cases: list[dict] = []
    for idx, tid in enumerate(selected, start=1):
        events = events_by_ticket.get(tid, [])
        deps = dep_engine.build(events)
        promised = None
        status = "OPEN"
        if tid in tickets.index:
            row = tickets.loc[tid]
            promised = pd.Timestamp(row["promised_date"]).to_pydatetime() if isinstance(row["promised_date"], str) else None
            status = str(row["current_status"])
        progress = state_engine.analyze(
            ticket_id=tid,
            ticket_status=status,
            promised_date=promised,
            events=events,
            deps=deps,
            now=reference_now(),
        )
        blocker = ""
        if progress.blockers:
            blocker = progress.blockers[0]
        elif progress.waiting_on:
            blocker = progress.waiting_on
        cases.append(
            {
                "case_id": f"E-{idx:03d}",
                "ticket_id": tid,
                "expected_state": progress.progress_state,
                "expected_blocker": blocker,
                "expected_next_action": progress.next_action or "",
                "expected_date_status": progress.date_status or "",
                "difficulty": _difficulty(progress.progress_state),
                "failure_case": _failure_case(events, progress.progress_state, progress.date_status),
                "human_understanding_score": "",
                "human_followup_required": "",
                "baseline_score": "",
                "prototype_score": "",
            }
        )
    return cases


def _difficulty(state: str) -> str:
    if state in ("WAITING_FOR_VENDOR", "BLOCKED", "DELAYED", "REOPENED", "TRANSFERRED"):
        return "hard"
    if state in ("WAITING_FOR_APPROVAL", "WAITING_FOR_INTERNAL_TEAM", "WAITING_FOR_CUSTOMER"):
        return "medium"
    return "normal"


def main() -> None:
    events = _load_events()
    tickets = pd.read_csv(RAW / "tickets.csv")
    cases = _build_cases(events, tickets)
    if len(cases) < MIN_CASES:
        raise SystemExit(f"not enough cases: {len(cases)} < {MIN_CASES}")
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(cases)
    df.to_csv(OUT / "evaluation_cases.csv", index=False)
    print(f"evaluation cases written: {len(cases)} cases -> {OUT / 'evaluation_cases.csv'}")


if __name__ == "__main__":
    main()