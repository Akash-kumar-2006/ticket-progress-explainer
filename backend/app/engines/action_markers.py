"""Action-marker lexicon for grounded next-action prediction.

The Progress State Engine historically emitted a small set of fixed next-action
sentences and ignored the wording of the recorded work notes. This module adds a
maintainable, data-driven lexicon that maps phrases found in *actual ticket
events* to a small set of action categories, and renders a customer-facing
sentence from the matched event.

Design constraints (kept deliberately strict so the anti-hallucination contract
is preserved):

* A signal is only produced when a marker phrase is literally present in the
  text of a real event. Nothing is inferred from a missing field.
* Every signal carries the ``event_id`` of the event that produced it, so the
  claim stays traceable exactly like the status and blocker claims.
* Categories are evaluated in ``ACTION_PRIORITY`` order and the most recent
  matching event wins, so a later "approved" note is not overwritten by an
  older "pending approval" note.
* When the evidence is too sparse to justify any specific action the engine
  returns an explicit *status-confirmation* signal instead of inventing work.
  This is the same safety net already used for explanations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import DependencyInfo, EventData

# Minimum number of events before we are willing to state a specific action.
SPARSE_EVENT_THRESHOLD = 2

# Event types that can carry an actionable message.
ACTIONABLE_EVENT_TYPES = (
    "WORK_NOTE",
    "VENDOR_UPDATE",
    "APPROVAL_REQUESTED",
    "DEPENDENCY_CREATED",
    "TEAM_TRANSFER",
    "CUSTOMER_UPDATE",
    "ASSIGNMENT_CHANGE",
    "STATUS_CHANGE",
)

# After a ticket is resolved or reopened, older action markers are not a
# reliable guide to what happens next.
TERMINAL_EVENT_TYPES = ("RESOLUTION", "REOPENED")


@dataclass(frozen=True)
class ActionCategory:
    """One action category: what to look for, and how to phrase it."""

    key: str
    label: str
    markers: tuple[str, ...]
    template: str
    states: tuple[str, ...] = ()
    #: Filler for "{detail}"; taken from dependency/approval/vendor context.
    detail: str = ""


# Order matters: the first category with a marker hit wins, so specific
# operational categories are listed before broad ones.
ACTION_CATEGORIES: tuple[ActionCategory, ...] = (
    ActionCategory(
        key="APPROVAL",
        label="Pending approval",
        markers=(
            "pending approval",
            "approval required",
            "awaiting approval",
            "awaiting sign-off",
            "pending sign-off",
            "manager approval",
            "security review",
            "security approval",
            "approval is being",
            "requesting approval",
        ),
        template="{owner} must complete the pending {detail} approval.",
    ),
    ActionCategory(
        key="VENDOR_RESPONSE",
        label="Waiting for vendor",
        markers=(
            "waiting for vendor",
            "awaiting vendor",
            "vendor response",
            "vendor follow-up",
            "vendor confirmation",
            "awaiting shipment",
            "awaiting dispatch",
            "replacement part",
            "part delivery",
            "vendor to provide",
        ),
        template="The vendor must confirm dispatch or delivery of the {detail}.",
    ),
    ActionCategory(
        key="CUSTOMER_RESPONSE",
        label="Waiting for customer",
        markers=(
            "waiting on customer",
            "waiting for customer",
            "awaiting customer",
            "awaiting reply",
            "customer confirmation",
            "customer to provide",
            "customer to confirm",
            "need more info from customer",
            "requested information from the customer",
        ),
        template="The customer must provide the requested information or confirmation.",
    ),
    ActionCategory(
        key="ESCALATION",
        label="Escalation required",
        markers=(
            "escalat",
            "senior review",
            "management review",
            "supervisor review",
            "priority escalation",
        ),
        template="The request must be escalated to the next level of support.",
    ),
    ActionCategory(
        key="REASSIGNMENT",
        label="Reassignment required",
        markers=(
            "reassign",
            "re-assign",
            "hand off",
            "hand-off",
            "handing off",
            "hands off",
            "handover",
            "hand over",
            "transfer to",
            "routing to",
            "forwarded to",
            "assign to regional",
        ),
        template="The request must be reassigned to the team that will continue the work.",
    ),
    ActionCategory(
        key="VERIFICATION",
        label="Verification required",
        # Evaluated before DEPLOYMENT on purpose: a note such as "verify the fix
        # once deployed" is a verification step that merely mentions a
        # deployment, and should not be classified as the deployment itself.
        markers=(
            "verify",
            "verification",
            "validate",
            "validation",
            "retest",
            "re-test",
            "monitor the",
            "confirm the fix",
            "test the",
        ),
        template="The change must be verified and the outcome confirmed.",
    ),
    ActionCategory(
        key="DEPLOYMENT",
        label="Deployment or change",
        markers=(
            "deploy",
            "deployment",
            "patch",
            "rollout",
            "roll out",
            "release window",
            "maintenance window",
            "change window",
            "configuration update",
        ),
        template="The scheduled change or deployment must be applied in the next available window.",
    ),
    ActionCategory(
        key="INFORMATION",
        label="Information or logs required",
        markers=(
            "provide logs",
            "collect logs",
            "review logs",
            "provide information",
            "collect evidence",
            "additional information",
            "diagnostic data",
            "provide attachment",
            "screenshots",
            "reproduce issue",
        ),
        template="The requested logs and information must be collected and shared.",
    ),
    ActionCategory(
        key="INVESTIGATION",
        label="Investigation required",
        markers=(
            "investigat",
            "troubleshoot",
            "diagnost",
            "root cause",
            "reproduc",
        ),
        template="The support team must complete the investigation and identify the cause.",
    ),
    ActionCategory(
        key="FOLLOW_UP",
        label="Customer follow-up",
        markers=(
            "follow up with the customer",
            "following up with the customer",
            "update the customer",
            "update requester",
            "keep the customer informed",
            "keep customer informed",
        ),
        template="The support team must follow up with the customer on the latest status.",
    ),
    ActionCategory(
        key="CLOSURE",
        label="Closure",
        markers=(
            "close the ticket",
            "close ticket",
            "confirm resolution",
            "resolve the request",
            "confirm the fix and close",
        ),
        template="The request must be closed once the completed work is confirmed.",
    ),
)

CATEGORY_BY_KEY = {c.key: c for c in ACTION_CATEGORIES}

#: Safe fallback used when the evidence cannot justify a specific action.
STATUS_CONFIRMATION = ActionCategory(
    key="STATUS_CONFIRMATION",
    label="Status confirmation",
    markers=(),
    template="The support team is confirming the current status and will update you once the next step is clear.",
)


@dataclass
class ActionSignal:
    """A grounded next-action suggestion."""

    text: str
    evidence_ids: list[str] = field(default_factory=list)
    category: str = ""
    confidence: str = "specific"  # specific | generic | sparse
    reason: str = ""

    def __bool__(self) -> bool:
        return bool(self.text and self.evidence_ids)


def find_category(message: str) -> ActionCategory | None:
    """Return the first category whose marker appears in ``message``."""
    if not message:
        return None
    text = message.lower()
    for category in ACTION_CATEGORIES:
        for marker in category.markers:
            if marker in text:
                return category
    return None


def _detail_for(category: ActionCategory, events: list[EventData], deps: list[DependencyInfo]) -> str:
    """Fill the {detail} slot from real dependency/vendor context."""
    if category.key == "APPROVAL":
        for e in events:
            if e.event_type == "APPROVAL_REQUESTED" and e.approval_type:
                return e.approval_type.lower()
        for d in deps:
            if d.kind == "approval":
                return d.title.replace(" approval", "").lower() or "requested"
        return "requested"
    if category.key == "VENDOR_RESPONSE":
        for e in events:
            if e.event_type == "VENDOR_UPDATE" and e.vendor_item:
                return str(e.vendor_item).lower()
        for e in events:
            if e.event_type == "VENDOR_UPDATE" and e.vendor:
                return f"items from {e.vendor}"
        return "required items"
    return category.detail


def _owner_for(category: ActionCategory, events: list[EventData], deps: list[DependencyInfo]) -> str:
    if category.key == "APPROVAL":
        pending = [d for d in deps if d.kind == "approval" and d.status != "completed"]
        if pending:
            return pending[0].owner
        for e in events:
            if e.event_type == "APPROVAL_REQUESTED" and e.team:
                return e.team
        return "the approval team"
    if category.key == "VENDOR_RESPONSE":
        pending = [d for d in deps if d.kind == "vendor" and d.status != "completed"]
        if pending:
            return pending[0].owner
        return "Vendor Operations"
    if category.key == "REASSIGNMENT":
        for e in events:
            if e.event_type == "TEAM_TRANSFER" and e.team:
                return e.team
        return "the receiving team"
    for d in deps:
        if d.status != "completed" and d.owner:
            return d.owner
    for e in events:
        if e.team:
            return e.team
    return "The support team"


def _relevant_events(events: list[EventData]) -> list[EventData]:
    """Events that can inform the next action.

    Everything before the last resolution/reopen is dropped, and anything without
    a message is ignored because a marker must be read from real text.
    """
    actionable = [e for e in events if e.event_type in ACTIONABLE_EVENT_TYPES and (e.message or "").strip()]
    if not actionable:
        return []
    last_terminal = None
    for e in events:
        if e.event_type in TERMINAL_EVENT_TYPES:
            if last_terminal is None or e.timestamp > last_terminal.timestamp:
                last_terminal = e
    if last_terminal is not None:
        actionable = [e for e in actionable if e.timestamp > last_terminal.timestamp]
    return sorted(actionable, key=lambda e: (e.timestamp, e.event_id))


def infer_action(
    events: list[EventData],
    deps: list[DependencyInfo],
    state: str,
) -> ActionSignal | None:
    """Infer a grounded next action for a ticket.

    Returns ``None`` when no marker is found in real event text, so the caller
    can keep its existing state-specific sentence. Returns a *sparse* signal
    when there is some evidence but not enough to name a specific action.
    """
    candidates = _relevant_events(events)
    if not candidates:
        return None

    for event in reversed(candidates):
        category = find_category(event.message or "")
        if category is not None:
            detail = _detail_for(category, events, deps)
            owner = _owner_for(category, events, deps)
            text = category.template.format(owner=owner, detail=detail)
            return ActionSignal(
                text=text,
                evidence_ids=[event.event_id],
                category=category.key,
                confidence="specific",
                reason=f"marker '{_matched_marker(event.message or '', category)}' in {event.event_type}",
            )

    # Evidence exists but names no specific action.
    if len(events) < SPARSE_EVENT_THRESHOLD:
        return ActionSignal(
            text=STATUS_CONFIRMATION.template,
            evidence_ids=[candidates[-1].event_id],
            category=STATUS_CONFIRMATION.key,
            confidence="sparse",
            reason="too few events to justify a specific next action",
        )
    return None


def _matched_marker(message: str, category: ActionCategory) -> str:
    text = (message or "").lower()
    for marker in category.markers:
        if marker in text:
            return marker
    return category.key.lower()
