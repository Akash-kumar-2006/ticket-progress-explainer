"""Progress State Engine.

Determines a transparent, evidence-backed progress state for a ticket using:
- effective status (latest valid STATUS_CHANGE / RESOLUTION / REOPENED event)
- incomplete dependencies (approval / vendor / customer / internal)
- blocked dependencies / vendor updates
- recent regional transfers
- promised-date overdue status

The rule order is documented in docs/ARCHITECTURE.md.
"""
from datetime import datetime, timedelta

from ..engines.date_risk import DateRiskEngine
from ..engines.dependency import DependencyEngine, CUSTOMER_WAIT_MARKERS
from ..engines.grounding import _status_conflicts
from ..engines.models import DateAnalysis, DependencyInfo, EventData, ProgressResult

RECENT_TRANSFER_WINDOW = timedelta(hours=72)


class ProgressStateEngine:
    def __init__(self):
        self._date_engine = DateRiskEngine()

    @staticmethod
    def effective_status(ticket_status: str | None, events: list[EventData]) -> str:
        terminal = [e for e in events if e.event_type in ("STATUS_CHANGE", "RESOLUTION", "REOPENED")]
        terminal_sorted = sorted(terminal, key=lambda e: (e.timestamp, e.event_id))
        if not terminal_sorted:
            return ticket_status or "OPEN"
        last = terminal_sorted[-1]
        if last.event_type == "RESOLUTION":
            return "RESOLVED"
        if last.event_type == "REOPENED":
            return "REOPENED"
        return last.new_status or ticket_status or "OPEN"

    def analyze(
        self,
        ticket_id: str,
        ticket_status: str | None,
        promised_date: datetime | None,
        events: list[EventData],
        deps: list[DependencyInfo],
        now: datetime,
    ) -> ProgressResult:
        eff_status = self.effective_status(ticket_status, events)
        reasons: list[str] = []

        conflicts = _status_conflicts(events)
        if conflicts:
            reasons.append(
                f"Data conflict detected: {len(conflicts)} event(s) reversed a resolved status"
            )

        pending_approvals = DependencyEngine.incomplete(deps, "approval")
        pending_vendors = DependencyEngine.incomplete(deps, "vendor")
        pending_customers = DependencyEngine.incomplete(deps, "customer")
        blocked_list = [d for d in pending_approvals + pending_vendors if d.status == "blocked"]
        if not blocked_list:
            blocked_list = [d for d in deps if d.status == "blocked"]
        any_pending = [d for d in deps if d.status in ("pending", "blocked")]

        # ---- RESOLVED / REOPENED ----
        if eff_status == "RESOLVED":
            reasons.append("Latest valid event set the ticket to RESOLVED")
            dres = self._date(promised_date, True, "RESOLVED", events, now)
            return self._result(
                ticket_id, "RESOLVED", eff_status, dres, promised_date, events, reasons,
                next_action="No further action is required.",
            )

        if eff_status == "REOPENED":
            reasons.append("Ticket was reopened after being resolved")
            dres = self._date(promised_date, False, "REOPENED", events, now)
            return self._result(
                ticket_id, "REOPENED", eff_status, dres, promised_date, events, reasons,
                next_action="The support team is reviewing the reopened request.",
            )

        # ---- Waiting states from dependencies ----
        if pending_approvals:
            a = pending_approvals[0]
            reasons.append(f"Unresolved approval dependency: {a.title}")
            blockers = [d.title for d in blocked_list]
            dres = self._date(promised_date, False, "WAITING_FOR_APPROVAL", events, now)
            return self._result(
                ticket_id, "WAITING_FOR_APPROVAL", eff_status, dres, promised_date, events,
                reasons, blockers=blockers, waiting_on=a.owner,
                next_action=f"{a.owner} needs to complete the {a.title}.",
                next_action_evidence=[a.source_event_id],
            )

        if pending_vendors:
            v = pending_vendors[0]
            reasons.append(f"Unresolved vendor dependency: {v.title}")
            dres = self._date(promised_date, False, "WAITING_FOR_VENDOR", events, now)
            blockers = [d.title for d in blocked_list] or [
                v.title if v.status == "blocked" else ""
            ]
            return self._result(
                ticket_id,
                "BLOCKED" if v.status == "blocked" else "WAITING_FOR_VENDOR",
                eff_status,
                dres,
                promised_date,
                events,
                reasons,
                blockers=[b for b in blockers if b],
                waiting_on="Vendor Operations",
                next_action=f"The vendor is expected to provide: {v.title.split('from ')[-1]}.",
                next_action_evidence=[v.source_event_id],
            )

        if pending_customers:
            c = pending_customers[0]
            reasons.append("Waiting on information from the customer")
            dres = self._date(promised_date, False, "WAITING_FOR_CUSTOMER", events, now)
            return self._result(
                ticket_id, "WAITING_FOR_CUSTOMER", eff_status, dres, promised_date, events,
                reasons, waiting_on="Customer",
                next_action="The customer needs to provide the requested information.",
                next_action_evidence=[c.source_event_id],
            )

        if blocked_list:
            b = blocked_list[0]
            reasons.append(f"Dependency is blocked: {b.title}")
            dres = self._date(promised_date, False, "BLOCKED", events, now)
            return self._result(
                ticket_id, "BLOCKED", eff_status, dres, promised_date, events, reasons,
                blockers=[d.title for d in blocked_list], waiting_on=b.owner,
                next_action=f"The blocker ({b.title}) must be removed by {b.owner}.",
                next_action_evidence=[b.source_event_id],
            )

        if any_pending:
            p = any_pending[0]
            reasons.append(f"Internal dependency pending: {p.title}")
            dres = self._date(promised_date, False, "WAITING_FOR_INTERNAL_TEAM", events, now)
            return self._result(
                ticket_id, "WAITING_FOR_INTERNAL_TEAM", eff_status, dres, promised_date, events,
                reasons, waiting_on=p.owner,
                next_action=f"{p.owner} is continuing work on {p.title}.",
                next_action_evidence=[p.source_event_id],
            )

        # ---- Overdue (unresolved, no active waiting dependency) ----
        dres = self._date(promised_date, False, eff_status, events, now)
        if dres.date_status == "OVERDUE":
            reasons.append("Overdue: promised date passed, ticket unresolved, no active wait dependency")
            return self._result(
                ticket_id, "DELAYED", eff_status, dres, promised_date, events, reasons,
                next_action="The schedule needs to be reviewed and an updated completion date confirmed.",
            )

        # ---- Recent transfer ----
        if self._recent_transfer(events, now):
            reasons.append("Regional team transfer happened recently")
            return self._result(
                ticket_id, "TRANSFERRED", eff_status, dres, promised_date, events, reasons,
                next_action="The receiving team is taking over the request.",
            )

        # ---- Generic status ----
        if eff_status == "IN_PROGRESS":
            if self._scheduled(events):
                reasons.append("Latest work note schedules the next action")
                return self._result(
                    ticket_id, "SCHEDULED", eff_status, dres, promised_date, events, reasons,
                    next_action="The scheduled action is being executed.",
                )
            reasons.append("Ticket is in progress with no unresolved dependencies")
            return self._result(
                ticket_id, "IN_PROGRESS", eff_status, dres, promised_date, events, reasons,
                next_action="Work is continuing on the ticket.",
            )

        if eff_status == "OPEN":
            reasons.append("Ticket is open with no recorded activity beyond assignment")
            return self._result(
                ticket_id, "INVESTIGATING", eff_status, dres, promised_date, events, reasons,
                next_action="The assigned team is starting the investigation.",
            )

        # PENDING / ESCALATED default
        reasons.append(f"No specific blocker recorded; status is {eff_status}")
        return self._result(
            ticket_id, _map_default_state(eff_status), eff_status, dres, promised_date, events,
            reasons,
            next_action="The support team is continuing to work on the request.",
        )

    # ------------------------------------------------------------------
    def _date(self, promised, resolved, state, events, now) -> DateAnalysis:
        return self._date_engine.analyze(promised, resolved, state, events, now)

    def _result(
        self,
        ticket_id,
        state,
        eff_status,
        date_analysis: DateAnalysis,
        promised_date,
        events,
        reasons,
        blockers=None,
        waiting_on=None,
        next_action=None,
        next_action_evidence=None,
    ) -> ProgressResult:
        ev_ids = [e.event_id for e in events]
        if next_action_evidence is None:
            latest = max(events, key=lambda e: (e.timestamp, e.event_id), default=None)
            next_action_evidence = [latest.event_id] if latest else []
        return ProgressResult(
            ticket_id=ticket_id,
            progress_state=state,
            effective_status=eff_status,
            date_status=date_analysis.date_status,
            risk=date_analysis.risk,
            days_remaining=date_analysis.days_remaining,
            overdue_days=date_analysis.overdue_days,
            promised_date=promised_date,
            next_action=next_action,
            next_action_evidence=next_action_evidence or [],
            reasons=reasons,
            evidence_ids=ev_ids,
            blockers=blockers or [],
            waiting_on=waiting_on,
        )

    @staticmethod
    def _recent_transfer(events: list[EventData], now: datetime) -> bool:
        transfers = [e for e in events if e.event_type == "TEAM_TRANSFER"]
        if not transfers:
            return False
        latest_transfer = max(transfers, key=lambda e: e.timestamp)
        if now - latest_transfer.timestamp > RECENT_TRANSFER_WINDOW:
            return False
        after = [
            e
            for e in events
            if e.timestamp > latest_transfer.timestamp
            and e.event_type in ("WORK_NOTE", "STATUS_CHANGE", "RESOLUTION")
        ]
        return not after

    @staticmethod
    def _scheduled(events: list[EventData]) -> bool:
        notes = [e for e in events if e.event_type == "WORK_NOTE"]
        if not notes:
            return False
        latest = max(notes, key=lambda e: e.timestamp)
        return "schedul" in (latest.message or "").lower()


def _map_default_state(status: str) -> str:
    mapping = {
        "PENDING": "IN_PROGRESS",
        "ESCALATED": "IN_PROGRESS",
        "REOPENED": "REOPENED",
        "RESOLVED": "RESOLVED",
    }
    return mapping.get(status, "IN_PROGRESS")