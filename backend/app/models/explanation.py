from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class GeneratedExplanation(Base):
    __tablename__ = "generated_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    current_state: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    explanation: Mapped[str] = mapped_column(Text)
    grounding_score: Mapped[float] = mapped_column(Float, default=0.0)
    date_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk: Mapped[str | None] = mapped_column(String(32), nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    promised_date: Mapped[datetime | None] = mapped_column(nullable=True)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    model_version: Mapped[str] = mapped_column(String(64))
    rules_version: Mapped[str] = mapped_column(String(64))
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ExplanationEvidence(Base):
    __tablename__ = "explanation_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    explanation_id: Mapped[int] = mapped_column(
        ForeignKey("generated_explanations.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(128))
    position: Mapped[int] = mapped_column(Integer, default=0)