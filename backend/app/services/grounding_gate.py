"""Grounding and refusal gate for any explanation generator.

This is a *validation layer around* the existing generators - it does not
replace or re-implement them, and it does not make the optional LLM generator
mandatory. The rule-based generator produces the grounded claim set; an LLM
generator would be expected to re-word it. In both cases this gate verifies the
output before it is allowed to reach a customer.

What the gate checks
--------------------
1. Grounding  - every claim must cite at least one real event id of the ticket,
   and every cited id must actually exist on that ticket.
2. No invented facts - the rendered text must not assert a completion, a date,
   an approval, a vendor response or a customer communication that is absent
   from the ticket evidence.
3. Refusal     - when the system itself reports insufficient evidence, the text
   must be a refusal/uncertainty statement and must not contain a confident
   next action.

The gate returns a structured report rather than raising, so callers can decide
what to do; :func:`assert_grounded` is provided for tests and CI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..engines.models import ExplanationPayload, EventData

#: Phrases that assert an outcome. Each entry maps to the evidence that would be
#: required for the assertion to be allowed.
COMPLETION_PHRASES = (
    "has been resolved",
    "was resolved",
    "is resolved",
    "has been fixed",
    "issue is fixed",
    "problem is fixed",
    "request is complete",
    "has been completed",
    "ticket is closed",
    "has been closed",
)

DATE_PHRASES = (
    "will be resolved by",
    "will be completed by",
    "will be fixed by",
    "guaranteed by",
    "resolved on",
    "fixed on",
    "completed on",
)

APPROVAL_PHRASES = (
    "approval has been granted",
    "approval was granted",
    "has been approved",
    "was approved",
    "approval is complete",
)

VENDOR_PHRASES = (
    "vendor has shipped",
    "vendor shipped",
    "part has arrived",
    "part arrived",
    "vendor has confirmed",
    "delivery completed",
)

CUSTOMER_CONTACT_PHRASES = (
    "we called you",
    "we have called",
    "we emailed you",
    "we have emailed",
    "we spoke with you",
    "you confirmed",
    "you have confirmed",
    "customer has confirmed",
)

UNSUPPORTED_GROUPS = {
    "completion": COMPLETION_PHRASES,
    "date": DATE_PHRASES,
    "approval": APPROVAL_PHRASES,
    "vendor": VENDOR_PHRASES,
    "customer_contact": CUSTOMER_CONTACT_PHRASES,
}

#: Text that is acceptable when the system refuses to answer.
REFUSAL_MARKERS = (
    "do not provide enough information",
    "not enough information",
    "cannot be determined",
    "unable to determine",
    "cannot reliably",
    "not able to determine",
)

REFUSAL_TEXT = (
    "Your ticket is currently in progress. The available updates do not provide "
    "enough information to reliably explain the next step."
)


@dataclass
class GroundingReport:
    """Outcome of a single gate run."""

    passed: bool
    checks: list[str] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    refused: bool = False

    def add(self, name: str, ok: bool, detail: str = "", **extra) -> None:
        self.checks.append(f"{name}: {'PASS' if ok else 'FAIL'}{(' - ' + detail) if detail else ''}")
        if not ok:
            self.violations.append({"check": name, "detail": detail, **extra})

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "refused": self.refused,
            "checks": self.checks,
            "violations": self.violations,
        }


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _has_any(text: str, phrases) -> str:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return ""


def check_grounding(
    payload: ExplanationPayload,
    events: list[EventData],
    *,
    allow_invented_completion: bool = False,
) -> GroundingReport:
    """Validate a generated explanation against the ticket it describes."""
    report = GroundingReport(passed=True)
    real_ids = {e.event_id for e in events}

    # 1. Every claim must cite at least one real event of this ticket.
    unsupported = [c.text for c in payload.claims if not c.supported or not c.evidence]
    report.add(
        "claims_have_evidence",
        not unsupported,
        f"{len(unsupported)} claim(s) without evidence",
        claims=unsupported,
    )

    unknown = sorted({
        eid for c in payload.claims for eid in c.evidence if eid not in real_ids
    })
    report.add(
        "evidence_exists_on_ticket",
        not unknown,
        f"unknown event id(s): {unknown}",
        unknown_event_ids=unknown,
    )

    next_action_ev = list(payload.next_action_evidence or [])
    dangling = [eid for eid in next_action_ev if eid not in real_ids]
    report.add(
        "next_action_evidence_exists",
        not dangling,
        f"unknown event id(s): {dangling}",
        unknown_event_ids=dangling,
    )

    # 2. No invented facts in the customer-visible text.
    text = _normalise(payload.explanation)
    if not allow_invented_completion and not _evidence_supports_completion(events):
        hit = _has_any(text, COMPLETION_PHRASES)
        report.add(
            "no_invented_completion",
            not hit,
            f"asserts '{hit}' but no resolution evidence exists",
            group="completion",
        )

    for group, phrases in UNSUPPORTED_GROUPS.items():
        if group == "completion":
            continue
        hit = _has_any(text, phrases)
        report.add(f"no_invented_{group}", not hit, f"asserts '{hit}'" if hit else "", group=group)

    # 3. Refusal behaviour when the system is unsure.
    insufficient = bool(payload.insufficient_evidence)
    report.refused = insufficient
    if insufficient:
        is_refusal = any(marker in text for marker in REFUSAL_MARKERS) or not text.strip()
        report.add("refusal_is_explicit", is_refusal, "insufficient_evidence set but text asserts facts")
        # A concrete, evidence-backed action is a confident claim and must not be
        # made while the system admits it lacks information. Only a generic
        # "we are confirming" message is acceptable here.
        safe_action = (
            not payload.next_action
            or payload.next_action_category == "STATUS_CONFIRMATION"
            or _is_status_confirmation(payload.next_action)
        )
        report.add(
            "no_confident_action_when_unsure",
            safe_action,
            f"next action stated while evidence is insufficient: {payload.next_action!r}",
        )

    report.passed = not report.violations
    return report


def _is_status_confirmation(text: str) -> bool:
    """True when a next action only promises to confirm status, not new work."""
    t = _normalise(text)
    return ("confirm" in t or "clarify" in t or "check back" in t) and not any(
        phrase in t
        for group in UNSUPPORTED_GROUPS.values()
        for phrase in group
    )


def _evidence_supports_completion(events: list[EventData]) -> bool:
    for e in events:
        if e.event_type == "RESOLUTION":
            return True
        if e.event_type == "STATUS_CHANGE" and (e.new_status or "").upper() == "RESOLVED":
            return True
    return False


def assert_grounded(payload: ExplanationPayload, events: list[EventData]) -> GroundingReport:
    """Raise AssertionError when the payload fails the gate (used by tests/CI)."""
    report = check_grounding(payload, events)
    if not report.passed:
        detail = "; ".join(
            f"{v['check']}({v.get('detail', '')})" for v in report.violations
        )
        raise AssertionError(f"grounding gate failed: {detail}")
    return report


def refuses_without_evidence(payload: ExplanationPayload) -> bool:
    """True when the payload declines to state a specific outcome."""
    if not payload.insufficient_evidence:
        return False
    text = _normalise(payload.explanation)
    return any(marker in text for marker in REFUSAL_MARKERS)
