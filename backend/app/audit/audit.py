from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models.audit import AuditLog


def log_audit(
    db: Session,
    actor: str,
    role: str,
    action: str,
    ticket_id: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    source: str = "api",
) -> AuditLog:
    """Record an auditable action. Never contains secrets."""
    entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        actor=actor,
        role=role,
        action=action,
        ticket_id=ticket_id,
        old_value=_safe_str(old_value),
        new_value=_safe_str(new_value),
        reason=_safe_str(reason),
        source=source,
        system_version=settings.model_version,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _safe_str(value) -> str | None:
    if value is None:
        return None
    return str(value)[:4000]