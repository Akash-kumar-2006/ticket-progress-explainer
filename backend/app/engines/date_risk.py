"""Promised-date analysis.

Deliberately claims OVERDUE only when the ticket is unresolved, and AT_RISK
only when there is *evidence* of a delay or an active waiting state close to
the promised date. Time passing alone is never treated as evidence.
"""
from datetime import datetime

from .models import DateAnalysis, EventData

DELAY_HINTS = [
    "delay",
    "delayed",
    "late",
    "backorder",
    "back order",
    "longer than expected",
    "behind schedule",
    "will arrive",
    "rescheduled",
]


class DateRiskEngine:
    def analyze(
        self,
        promised_date: datetime | None,
        is_resolved: bool,
        progress_state: str,
        events: list[EventData],
        now: datetime,
    ) -> DateAnalysis:
        if is_resolved:
            return DateAnalysis(
                date_status="COMPLETED", risk="COMPLETED", days_remaining=0, overdue_days=0
            )
        if promised_date is None:
            return DateAnalysis(date_status=None, risk="NO_DATE", days_remaining=None, overdue_days=0)

        days_remaining = (promised_date.date() - now.date()).days
        overdue_days = max(0, -days_remaining)
        reasons: list[str] = []
        delay_ev = [
            e
            for e in events
            if e.event_type == "VENDOR_UPDATE"
            and any(h in (e.message or "").lower() for h in DELAY_HINTS)
        ]

        if promised_date.date() < now.date():
            reasons.append("Promised date has passed and the ticket is unresolved")
            return DateAnalysis(
                date_status="OVERDUE",
                risk="OVERDUE",
                days_remaining=days_remaining,
                overdue_days=overdue_days,
                delay_evidence_ids=[e.event_id for e in delay_ev],
                reasons=reasons,
            )

        waiting_states = {
            "WAITING_FOR_VENDOR",
            "WAITING_FOR_APPROVAL",
            "WAITING_FOR_INTERNAL_TEAM",
            "BLOCKED",
            "WAITING_FOR_CUSTOMER",
        }

        if delay_ev:
            reasons.append("Vendor update indicates a delay")
            return DateAnalysis(
                date_status="AT_RISK",
                risk="AT_RISK",
                days_remaining=days_remaining,
                overdue_days=0,
                delay_evidence_ids=[e.event_id for e in delay_ev],
                reasons=reasons,
            )

        if progress_state in waiting_states and days_remaining <= 3:
            reasons.append(
                f"Ticket is waiting in state {progress_state} with {days_remaining} days remaining"
            )
            return DateAnalysis(
                date_status="AT_RISK",
                risk="AT_RISK",
                days_remaining=days_remaining,
                overdue_days=0,
                reasons=reasons,
            )

        # Promised date changed only because of a genuine schedule change -> still on track
        reasons.append("No evidence of delay; promised date has not passed")
        return DateAnalysis(
            date_status="ON_TRACK",
            risk="ON_TRACK",
            days_remaining=days_remaining,
            overdue_days=0,
            reasons=reasons,
        )