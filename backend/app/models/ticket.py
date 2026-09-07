from datetime import datetime, timezone

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_reference: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(8))
    region: Mapped[str] = mapped_column(String(64), index=True)
    current_team: Mapped[str] = mapped_column(String(64))
    current_status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    promised_date: Mapped[datetime | None] = mapped_column(nullable=True)
    actual_resolution_date: Mapped[datetime | None] = mapped_column(nullable=True)
    sla_status: Mapped[str] = mapped_column(String(32), default="ACTIVE")

    def to_dict(self, include_timestamps_iso: bool = True) -> dict:
        def iso(dt):
            return dt.isoformat() if dt else None

        return {
            "ticket_id": self.ticket_id,
            "customer_reference": self.customer_reference,
            "subject": self.subject,
            "category": self.category,
            "priority": self.priority,
            "region": self.region,
            "current_team": self.current_team,
            "current_status": self.current_status,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "promised_date": iso(self.promised_date),
            "actual_resolution_date": iso(self.actual_resolution_date),
            "sla_status": self.sla_status,
        }