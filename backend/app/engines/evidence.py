"""Evidence Selector.

Chooses the most relevant events that support a ticket's explanation, one per
semantic category (status, work note, transfer, approval, vendor, dependency,
date, resolution, assignment). Every selected item carries the reason it was
selected so the UI can show *why* each evidence event is cited.
"""
from ..engines.models import EvidenceItem, EventData, ProgressResult

CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("status", "Latest status change", ["STATUS_CHANGE"]),
    ("resolution", "Resolution activity", ["RESOLUTION"]),
    ("reopened", "Ticket reopened", ["REOPENED"]),
    ("work_note", "Latest work note", ["WORK_NOTE"]),
    ("transfer", "Latest regional transfer", ["TEAM_TRANSFER"]),
    ("approval", "Latest approval activity", ["APPROVAL_REQUESTED", "APPROVAL_COMPLETED"]),
    ("vendor", "Latest vendor update", ["VENDOR_UPDATE"]),
    ("dependency", "Latest dependency activity", ["DEPENDENCY_CREATED", "DEPENDENCY_COMPLETED"]),
    ("date", "Promised date event", ["PROMISED_DATE_SET", "PROMISED_DATE_CHANGED"]),
    ("assignment", "Latest assignment change", ["ASSIGNMENT_CHANGE"]),
    ("customer", "Update sent to customer", ["CUSTOMER_UPDATE"]),
]

PRIORITY_FOR_EXPLANATION = [
    "approval",
    "vendor",
    "status",
    "work_note",
    "dependency",
    "transfer",
    "date",
    "resolution",
    "reopened",
    "assignment",
    "customer",
]

MAX_EVIDENCE = 10


class EvidenceSelector:
    def select(self, events: list[EventData], progress: ProgressResult | None = None) -> list[EvidenceItem]:
        by_type: dict[str, list[EventData]] = {}
        for e in events:
            by_type.setdefault(e.event_type, []).append(e)

        picked: list[EvidenceItem] = []
        for category, reason, types in CATEGORIES:
            pool = []
            for t in types:
                pool.extend(by_type.get(t, []))
            if not pool:
                continue
            latest = max(pool, key=lambda e: (e.timestamp, e.event_id))
            picked.append(
                EvidenceItem(
                    event_id=latest.event_id,
                    event_type=latest.event_type,
                    timestamp=latest.timestamp,
                    text=latest.message or latest.label(),
                    reason=reason,
                    conflict_flag=latest.conflict_flag,
                )
            )

        # Deterministic priority order, cap the count
        order = {name: i for i, name in enumerate(PRIORITY_FOR_EXPLANATION)}
        picked.sort(key=lambda it: (order.get(_cat_for(it), 99), -it.timestamp.timestamp()))
        selected = picked[:MAX_EVIDENCE]

        # Anything the next-action claim cites must remain visible, even when a
        # newer event of the same type won the per-category slot. Without this a
        # perfectly grounded sentence could point at an event the reviewer is
        # not shown.
        required = sorted(set((progress.next_action_evidence if progress else None) or []))
        if required:
            present = {it.event_id for it in selected}
            by_id = {e.event_id: e for e in events}
            for eid in required:
                if eid in present:
                    continue
                ev = by_id.get(eid)
                if ev is None:
                    continue
                selected.append(
                    EvidenceItem(
                        event_id=ev.event_id,
                        event_type=ev.event_type,
                        timestamp=ev.timestamp,
                        text=ev.message or ev.label(),
                        reason="Supports the stated next action",
                        conflict_flag=ev.conflict_flag,
                    )
                )
        return selected


def _cat_for(item: EvidenceItem) -> str:
    for cat, _r, types in CATEGORIES:
        if item.event_type in types:
            return cat
    return "other"