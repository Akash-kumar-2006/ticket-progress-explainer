from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    role: Mapped[str] = mapped_column(String(32), default="SYSTEM")
    action: Mapped[str] = mapped_column(String(64), index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="api")
    system_version: Mapped[str] = mapped_column(String(64), default="")

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "role": self.role,
            "action": self.action,
            "ticket_id": self.ticket_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "source": self.source,
            "system_version": self.system_version,
        }