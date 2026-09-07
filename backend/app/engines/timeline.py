from .models import EventData, Timeline, TimelineEntry

EVENT_TITLES = {
    "STATUS_CHANGE": "Status change",
    "WORK_NOTE": "Work note",
    "TEAM_TRANSFER": "Team transfer",
    "APPROVAL_REQUESTED": "Approval requested",
    "APPROVAL_COMPLETED": "Approval completed",
    "VENDOR_UPDATE": "Vendor update",
    "PROMISED_DATE_SET": "Promised date set",
    "PROMISED_DATE_CHANGED": "Promised date changed",
    "DEPENDENCY_CREATED": "Dependency created",
    "DEPENDENCY_COMPLETED": "Dependency completed",
    "ASSIGNMENT_CHANGE": "Assignment change",
    "CUSTOMER_UPDATE": "Update sent to customer",
    "RESOLUTION": "Resolution",
    "REOPENED": "Ticket reopened",
}


class TimelineEngine:
    """Sorts events chronologically and builds a ticket timeline.

    Detects duplicate event IDs, events whose timestamps arrive out of order,
    and status-level conflicts.
    """

    def build(self, events: list[EventData], ticket_created=None) -> Timeline:
        # 1. Duplicate detection (same event_id seen more than once)
        seen: dict[str, int] = {}
        dups: list[str] = []
        for e in events:
            seen[e.event_id] = seen.get(e.event_id, 0) + 1
            if seen[e.event_id] == 2:
                dups.append(e.event_id)
        for e in events:
            if e.is_duplicate and e.event_id not in dups:
                dups.append(e.event_id)

        # 2. Out-of-order detection: timestamp must be non-decreasing in raw order
        out_of_order: list[str] = []
        running_max = None
        for e in events:
            if running_max is not None and e.timestamp < running_max:
                out_of_order.append(e.event_id)
            running_max = max(running_max or e.timestamp, e.timestamp)
        for e in events:
            if e.is_out_of_order and e.event_id not in out_of_order:
                out_of_order.append(e.event_id)

        # 3. Chronological sort (stable ties by raw order)
        ordered = sorted(enumerate(events), key=lambda kv: (kv[1].timestamp, kv[0]))

        entries: list[TimelineEntry] = []
        for idx, (raw_idx, e) in enumerate(ordered):
            flags: list[str] = []
            if e.event_id in dups:
                flags.append("duplicate")
            if e.event_id in out_of_order:
                flags.append("out_of_order")
            if e.conflict_flag:
                flags.append("conflict")
            if ticket_created is not None and e.timestamp < ticket_created:
                flags.append("before_ticket")
            entries.append(
                TimelineEntry(
                    index=idx,
                    event_id=e.event_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    title=EVENT_TITLES.get(e.event_type, e.event_type),
                    description=e.label(),
                    region=e.region,
                    team=e.team,
                    actor=(e.actor_type or "AGENT") + (f" {e.actor_id}" if e.actor_id else ""),
                    flags=flags,
                )
            )

        conflicts = self._detect_conflicts(events, dupes=set(dups))
        return Timeline(
            ticket_id=events[0].ticket_id if events else "",
            entries=entries,
            duplicates=sorted(set(dups)),
            out_of_order=sorted(set(out_of_order)),
            conflicts=conflicts,
            total=len(events),
        )

    @staticmethod
    def _detect_conflicts(events: list[EventData], dupes: set[str]) -> list[str]:
        """Detect contradictory status sequences (e.g. RESOLVED then IN_PROGRESS later)."""
        conflicts: list[str] = []
        status_events = sorted(
            [
                e
                for e in events
                if e.event_type == "STATUS_CHANGE"
                and e.new_status
                and e.event_id not in dupes
            ],
            key=lambda e: e.timestamp,
        )
        # RESOLVED jumps back to an unresolved status
        for prev, cur in zip(status_events, status_events[1:]):
            if prev.new_status == "RESOLVED" and cur.new_status in (
                "OPEN",
                "IN_PROGRESS",
                "PENDING",
                "ESCALATED",
                "REOPENED",
            ):
                conflicts.append(
                    f"{cur.event_id}: {cur.new_status} recorded after {prev.event_id} set RESOLVED"
                )
        return conflicts