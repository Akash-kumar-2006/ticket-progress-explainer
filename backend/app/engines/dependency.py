from datetime import datetime, timezone

from ..engines.models import DependencyInfo, EventData

DELAY_MARKERS = ["delay", "delayed", "late", "backorder", "back order", "longer than expected", "behind schedule"]
BLOCKED_MARKERS = ["blocked", "blocking", "on hold", "stalled"]
CUSTOMER_WAIT_MARKERS = ["waiting on customer", "awaiting customer", "need more info from customer", "customer to provide"]
VENDOR_WAIT_MARKERS = ["part", "component", "shipment", "delivery", "replacement", "stock"]

now_utc = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC (matches dataset timestamps)  # noqa: E731


class DependencyEngine:
    """Builds and tracks the dependency chain of a ticket.

    Dependencies come from three sources:
      1. Explicit DEPENDENCY_CREATED / DEPENDENCY_COMPLETED events.
      2. Approval events (APPROVAL_REQUESTED / APPROVAL_COMPLETED).
      3. Vendor updates (a delivery/inventory dependency inferred from the
         message content, e.g. "replacement part delayed").
    """

    def build(self, events: list[EventData]) -> list[DependencyInfo]:
        deps: dict[str, DependencyInfo] = {}

        def add(dep: DependencyInfo) -> None:
            deps.setdefault(dep.dependency_id, dep)

        # 1. Explicit dependencies
        for e in events:
            if e.event_type != "DEPENDENCY_CREATED":
                continue
            did = e.dependency_id or e.event_id
            status = "blocked" if any(m in (e.message or "").lower() for m in BLOCKED_MARKERS) else "pending"
            add(
                DependencyInfo(
                    dependency_id=did,
                    title=e.dependency_title or e.message or f"Task {did}",
                    kind=_kind_from_event(e),
                    status=status,
                    owner=e.dependency_owner or e.team or "Unknown",
                    created_at=e.timestamp,
                    source_event_id=e.event_id,
                )
            )

        for e in events:
            if e.event_type != "DEPENDENCY_COMPLETED" or not e.dependency_id:
                continue
            dep = deps.get(e.dependency_id)
            if dep:
                dep.status = "completed"
                dep.completed_at = e.timestamp

        for e in events:
            if e.event_type not in ("DEPENDENCY_BLOCKED", "DEPENDENCY_UNBLOCKED") or not e.dependency_id:
                continue
            dep = deps.get(e.dependency_id)
            if dep:
                dep.status = "blocked" if e.event_type == "DEPENDENCY_BLOCKED" else "pending"
                dep.latest_update_at = e.timestamp
                dep.latest_update_message = e.message

        # 2. Approvals
        for e in events:
            if e.event_type == "APPROVAL_REQUESTED":
                title = f"{e.approval_type or 'Requested'} approval"
                add(
                    DependencyInfo(
                        dependency_id=f"approval:{e.approval_type or 'general'}",
                        title=title,
                        kind="approval",
                        status="pending",
                        owner=e.team or "Approval team",
                        created_at=e.timestamp,
                        source_event_id=e.event_id,
                        latest_update_at=e.timestamp,
                        latest_update_message=e.message,
                    )
                )
            elif e.event_type == "APPROVAL_COMPLETED":
                dep = deps.get(f"approval:{e.approval_type or 'general'}")
                if dep:
                    dep.status = "completed"
                dep.completed_at = e.timestamp if dep else None

        # 3. Vendor / customer wait inferred from updates & work notes
        for e in events:
            msg = (e.message or "").lower()
            if e.event_type == "VENDOR_UPDATE":
                did = f"vendor:{e.vendor or 'vendor'}"
                status = "blocked" if any(m in msg for m in BLOCKED_MARKERS) else "pending"
                if did not in deps:
                    add(
                        DependencyInfo(
                            dependency_id=did,
                            title=f"Vendor delivery from {e.vendor or 'vendor'}",
                            kind="vendor",
                            status=status,
                            owner="Vendor Operations",
                            created_at=e.timestamp,
                            source_event_id=e.event_id,
                            latest_update_at=e.timestamp,
                            latest_update_message=e.message,
                        )
                    )
                else:
                    deps[did].status = status
                    deps[did].latest_update_at = e.timestamp
                    deps[did].latest_update_message = e.message
            elif e.event_type == "WORK_NOTE" and any(m in msg for m in CUSTOMER_WAIT_MARKERS):
                add(
                    DependencyInfo(
                        dependency_id="customer:info",
                        title="Information from customer",
                        kind="customer",
                        status="pending",
                        owner="Customer",
                        created_at=e.timestamp,
                        source_event_id=e.event_id,
                    )
                )

        result = sorted(deps.values(), key=lambda d: d.created_at)
        for d in result:
            end = d.completed_at or now_utc()
            d.age_days = round((end - d.created_at).total_seconds() / 86400.0, 1)
        return result

    @staticmethod
    def chain(deps: list[DependencyInfo]) -> list[dict]:
        """Return dependencies as an ordered list with visual state labels."""
        out = []
        for i, d in enumerate(deps):
            out.append(
                {
                    "position": i,
                    "dependency_id": d.dependency_id,
                    "title": d.title,
                    "kind": d.kind,
                    "status": d.status,
                    "owner": d.owner,
                    "created_at": d.created_at.isoformat(),
                    "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                    "age_days": d.age_days,
                    "source_event_id": d.source_event_id,
                    "latest_update_message": d.latest_update_message,
                }
            )
        return out

    @staticmethod
    def pending(deps: list[DependencyInfo]) -> list[DependencyInfo]:
        return [d for d in deps if d.status != "completed"]

    @staticmethod
    def blocked(deps: list[DependencyInfo]) -> list[DependencyInfo]:
        return [d for d in deps if d.status == "blocked"]

    @staticmethod
    def incomplete(deps: list[DependencyInfo], kind: str) -> list[DependencyInfo]:
        return [d for d in deps if d.status in ("pending", "blocked") and d.kind == kind]


def _kind_from_event(e: EventData) -> str:
    if e.approval_type or (e.dependency_id or "").startswith("approval:"):
        return "approval"
    if (e.dependency_id or "").startswith("vendor:") or e.vendor:
        return "vendor"
    owner = (e.dependency_owner or "").lower()
    if "vendor" in owner:
        return "vendor"
    if "customer" in owner:
        return "customer"
    return "internal"