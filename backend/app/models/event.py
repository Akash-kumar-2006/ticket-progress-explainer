from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    region: Mapped[str] = mapped_column(String(64))


class Region(Base):
    __tablename__ = "regions"

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="AGENT")
    actor_id: Mapped[str] = mapped_column(String(64), default="")
    region: Mapped[str] = mapped_column(String(64), default="")
    team: Mapped[str] = mapped_column(String(64), default="")
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    dependency_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dependency_title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dependency_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vendor_item: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approval_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    promised_date: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_out_of_order: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "ticket_id": self.ticket_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "region": self.region,
            "team": self.team,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "message": self.message,
            "dependency_id": self.dependency_id,
            "dependency_title": self.dependency_title,
            "dependency_owner": self.dependency_owner,
            "vendor": self.vendor,
            "vendor_item": self.vendor_item,
            "approval_type": self.approval_type,
            "promised_date": self.promised_date.isoformat() if self.promised_date else None,
            "is_duplicate": self.is_duplicate,
            "is_out_of_order": self.is_out_of_order,
            "conflict_flag": self.conflict_flag,
        }