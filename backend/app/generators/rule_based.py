"""Rule-Based Explanation Generator (default).

Assembles a customer-facing explanation exclusively from evidence-selected
events. Every sentence is produced with a list of supporting event IDs; if a
required claim has no supporting event the sentence is replaced by an explicit
uncertainty statement (anti-hallucination guard).
"""
from datetime import date, datetime

from ..engines.models import (
    DependencyInfo,
    EvidenceItem,
    ExplanationPayload,
    EventData,
    ProgressResult,
)
from .base import ExplanationGenerator

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def human_date(dt: datetime | date) -> str:
    return f"{_MONTHS[dt.month - 1]} {dt.day}"


class RuleBasedExplanationGenerator(ExplanationGenerator):
    name = "rule_based"

    def generate(
        self,
        *,
        ticket: dict,
        events: list[EventData],
        progress: ProgressResult,
        evidence,
        deps: list[DependencyInfo],
        now,
        grounding_score: int,
        grounding_breakdown: list[str],
        model_version: str,
        rules_version: str,
    ) -> ExplanationPayload:
        ev_by_type: dict[str, EvidenceItem] = {e.event_type: e for e in evidence}
        status_sentence, status_ev = self._status_sentence(ticket, progress, ev_by_type, events)

        claims = []
        insufficient = False

        if status_sentence is None or not status_ev:
            insufficient = True
        else:
            claims.append(_claim("status", status_sentence, [status_ev.event_id]))

        for text, ev_ids in self._progress_sentences(evidence, progress):
            if not ev_ids:
                continue
            claims.append(_claim("progress", text, ev_ids))

        for text, ev_ids in self._blocker_sentences(evidence, progress):
            claims.append(_claim("blocker", text, ev_ids))

        if progress.next_action:
            _append_next_action(claims, progress.next_action, progress.next_action_evidence)

        if not claims:
            return self._minimal_payload(ticket, progress, now, model_version, rules_version)

        date_sentence, date_ev = self._date_sentence(progress, ev_by_type)
        if date_sentence:
            claims.append(_claim("date", date_sentence, date_ev))

        # Anti-hallucination review: unsupported claims are dropped from the
        # final text. If the primary status claim cannot be evidenced, an
        # explicit uncertainty statement is shown instead of an invented fact.
        supported = [c for c in claims if c.supported]
        if insufficient and not any(c.category == "status" for c in supported):
            supported.insert(0, _claim(
                "status",
                "Your ticket is currently in progress. The available updates do not provide enough information to reliably explain the next step.",
                [],
            ))

        pieces = _join_with(supported)

        return ExplanationPayload(
            ticket_id=ticket["ticket_id"],
            progress_state=progress.progress_state,
            effective_status=progress.effective_status,
            date_status=progress.date_status,
            risk=progress.risk,
            grounding_score=grounding_score,
            grounding_breakdown=grounding_breakdown,
            explanation="\n\n".join(pieces) if pieces else self.generic_uncertainty(),
            claims=supported,
            evidence=evidence,
            next_action=progress.next_action,
            next_action_evidence=progress.next_action_evidence,
            promised_date=progress.promised_date,
            days_remaining=progress.days_remaining,
            insufficient_evidence=insufficient,
            conflicts=[c for c in (progress.reasons or []) if "conflict" in c.lower()],
            model_version=model_version,
            rules_version=rules_version,
            is_baseline=False,
        )

    # ------------------------------------------------------------------
    def _status_sentence(self, ticket, progress: ProgressResult, ev_by_type: dict[str, EvidenceItem], events: list[EventData]):
        state = progress.progress_state
        if state == "RESOLVED":
            ev = ev_by_type.get("RESOLUTION") or _latest_resolution(events)
            return "Your request has been resolved." if ev else None, ev
        if state == "REOPENED":
            ev = ev_by_type.get("REOPENED")
            return "Your previously resolved request has been reopened." if ev else None, ev
        if state == "WAITING_FOR_APPROVAL":
            ev = ev_by_type.get("APPROVAL_REQUESTED")
            if ev is None:
                return None, None
            return (
                f"Your request is currently waiting for approval from {progress.waiting_on or 'the responsible team'}.",
                ev,
            )
        if state in ("WAITING_FOR_VENDOR", "BLOCKED"):
            ev = ev_by_type.get("VENDOR_UPDATE") or _first_by_type(ev_by_type, "DEPENDENCY_CREATED")
            if ev is None:
                return None, None
            if state == "BLOCKED":
                return "Your request is currently blocked while a required component or action is unavailable.", ev
            vendor = getattr(ev, "text", "") or progress.waiting_on or "the vendor"
            return f"Your request is currently waiting for the vendor to provide the required item.", ev
        if state == "DELAYED":
            ev = _first_by_type(ev_by_type, "PROMISED_DATE_SET") or _first_by_type(ev_by_type, "PROMISED_DATE_CHANGED")
            return "Your request is currently delayed. The promised completion date has passed and the request is not yet resolved.", ev
        if state == "TRANSFERRED":
            ev = ev_by_type.get("TEAM_TRANSFER")
            if ev is None:
                return None, None
            return f"Your request has recently been transferred to a new support team.", ev
        if state in ("WAITING_FOR_CUSTOMER", "WAITING_FOR_INTERNAL_TEAM"):
            ev = _first_by_type(ev_by_type, "DEPENDENCY_CREATED") or _first_by_type(ev_by_type, "WORK_NOTE")
            if ev is None:
                return None, None
            what = "information from you" if state == "WAITING_FOR_CUSTOMER" else (progress.waiting_on or "an internal team")
            return f"Your request is currently waiting on {what}.", ev
        # IN_PROGRESS / SCHEDULED / INVESTIGATING / NEW
        ev = ev_by_type.get("WORK_NOTE") or ev_by_type.get("ASSIGNMENT_CHANGE") or _first_by_type(ev_by_type, "STATUS_CHANGE")
        if ev is None and ticket.get("current_team"):
            return (
                f"Your request is currently being handled by {ticket['current_team']}.",
                None,
            )
        if ev is None:
            return None, None
        return (
            f"Your request is currently being handled by {ticket.get('current_team', 'the support team')}.",
            ev,
        )

    def _progress_sentences(self, evidence, progress):
        out: list[tuple[str, list[str]]] = []
        completed_approval = _first_by_type({e.event_type: e for e in evidence}, "APPROVAL_COMPLETED")
        if completed_approval:
            out.append(
                (f"The required approval was completed on {human_date(completed_approval.timestamp)}.", [completed_approval.event_id])
            )
        transfer = _first_by_type({e.event_type: e for e in evidence}, "TEAM_TRANSFER")
        if transfer and progress.progress_state != "TRANSFERRED":
            out.append(
                (f"The request was transferred to a new team on {human_date(transfer.timestamp)}.", [transfer.event_id])
            )
        work_note = _first_by_type({e.event_type: e for e in evidence}, "WORK_NOTE")
        if work_note:
            note = work_note.text or work_note.reason
            snippet = note[:120] + ("..." if len(note) > 120 else "")
            out.append(
                (f"The support team provided an update: {snippet}", [work_note.event_id])
            )
        return out[:3]

    def _blocker_sentences(self, evidence, progress):
        out: list[tuple[str, list[str]]] = []
        if progress.blockers:
            for b in progress.blockers[:2]:
                ev = _first_by_type({e.event_type: e for e in evidence}, "VENDOR_UPDATE") or _first_by_type(
                    {e.event_type: e for e in evidence}, "DEPENDENCY_CREATED"
                )
                if ev:
                    out.append((f"Progress is currently blocked: {b}.", [ev.event_id]))
                else:
                    out.append((f"Progress is currently blocked: {b}.", []))
        elif progress.waiting_on and progress.progress_state in (
            "WAITING_FOR_APPROVAL",
            "WAITING_FOR_VENDOR",
            "WAITING_FOR_CUSTOMER",
            "WAITING_FOR_INTERNAL_TEAM",
        ):
            ev = _first_by_type({e.event_type: e for e in evidence}, "VENDOR_UPDATE") or _first_by_type(
                {e.event_type: e for e in evidence}, "APPROVAL_REQUESTED"
            ) or _first_by_type({e.event_type: e for e in evidence}, "DEPENDENCY_CREATED")
            out.append((f"Work is currently waiting for {progress.waiting_on}.", [ev.event_id] if ev else []))
        return out

    def _date_sentence(self, progress, ev_by_type):
        if progress.promised_date is None:
            return None, []
        promise_ev = _first_by_type(ev_by_type, "PROMISED_DATE_SET") or _first_by_type(ev_by_type, "PROMISED_DATE_CHANGED")
        promise_ev_id = [promise_ev.event_id] if promise_ev else []
        ds = progress.date_status
        base = f"Your promised completion date is {human_date(progress.promised_date)}"
        if ds == "COMPLETED":
            return f"{base}, and the request has been completed.", promise_ev_id
        if ds == "OVERDUE":
            return f"{base}. This date has passed and the request is still unresolved.", promise_ev_id
        if ds == "AT_RISK":
            ev = _first_by_type(ev_by_type, "VENDOR_UPDATE") or _first_by_type(ev_by_type, "APPROVAL_REQUESTED")
            return f"{base}, but based on the latest updates this date may not be met.", [ev.event_id] if ev else promise_ev_id
        return f"{base}. Based on the latest updates this date is currently still achievable.", promise_ev_id

    @staticmethod
    def generic_uncertainty() -> str:
        return "Your ticket is currently in progress. The available updates do not provide enough information to reliably explain the next step."

    def _minimal_payload(self, ticket, progress, now, model_version, rules_version) -> ExplanationPayload:
        return ExplanationPayload(
            ticket_id=ticket["ticket_id"],
            progress_state=progress.progress_state,
            effective_status=progress.effective_status,
            date_status=progress.date_status,
            risk=progress.risk,
            grounding_score=0,
            grounding_breakdown=["No evidence available"],
            explanation=self.generic_uncertainty(),
            claims=[],
            evidence=[],
            next_action=progress.next_action,
            next_action_evidence=[],
            promised_date=progress.promised_date,
            insufficient_evidence=True,
            model_version=model_version,
            rules_version=rules_version,
            is_baseline=False,
        )

    @staticmethod
    def _generic_status_sentence(ticket) -> str:
        return f"Your request is currently being handled by {ticket.get('current_team', 'the support team')}."


def _claim(category, text, ev_ids) -> "Claim":
    from ..engines.models import Claim

    return Claim(category=category, text=text, evidence=[i for i in ev_ids if i], supported=bool(ev_ids))


def _append_next_action(claims, next_action: str, ev_ids: list[str]) -> bool:
    text = f"The next expected action is: {next_action}"
    claims.append(_claim("next_action", text, ev_ids))
    return bool(ev_ids)


def _join_with(claims) -> list[str]:
    paragraph_names = ["status", "progress", "blocker", "next_action", "date"]
    blocks: list[str] = []
    for p in paragraph_names:
        items = [c.text for c in claims if c.category == p]
        if items:
            blocks.append(" ".join(items))
    return blocks


def _first_by_type(ev_by_type: dict[str, EvidenceItem], event_type: str):
    return ev_by_type.get(event_type)


def _latest_resolution(events: list[EventData]):
    resolutions = [e for e in events if e.event_type == "RESOLUTION"]
    if not resolutions:
        statuses = [
            e for e in events if e.event_type == "STATUS_CHANGE" and e.new_status == "RESOLVED"
        ]
        resolutions = statuses
    return max(resolutions, key=lambda e: (e.timestamp, e.event_id)) if resolutions else None