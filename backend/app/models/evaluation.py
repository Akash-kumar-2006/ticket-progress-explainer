from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime)
    evaluation_type: Mapped[str] = mapped_column(String(32), default="synthetic")
    num_cases: Mapped[int] = mapped_column(Integer, default=0)
    baseline_mean_understanding: Mapped[float] = mapped_column(Float, default=0.0)
    prototype_mean_understanding: Mapped[float] = mapped_column(Float, default=0.0)
    understanding_improvement_abs: Mapped[float] = mapped_column(Float, default=0.0)
    understanding_improvement_pct: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_followup_rate: Mapped[float] = mapped_column(Float, default=0.0)
    prototype_followup_rate: Mapped[float] = mapped_column(Float, default=0.0)
    followup_reduction_pct: Mapped[float] = mapped_column(Float, default=0.0)
    state_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    blocker_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    next_action_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    promised_date_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    grounding_accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_at": self.run_at.isoformat(),
            "evaluation_type": self.evaluation_type,
            "num_cases": self.num_cases,
            "baseline_mean_understanding": self.baseline_mean_understanding,
            "prototype_mean_understanding": self.prototype_mean_understanding,
            "understanding_improvement_abs": self.understanding_improvement_abs,
            "understanding_improvement_pct": self.understanding_improvement_pct,
            "baseline_followup_rate": self.baseline_followup_rate,
            "prototype_followup_rate": self.prototype_followup_rate,
            "followup_reduction_pct": self.followup_reduction_pct,
            "state_accuracy": self.state_accuracy,
            "blocker_accuracy": self.blocker_accuracy,
            "next_action_accuracy": self.next_action_accuracy,
            "promised_date_accuracy": self.promised_date_accuracy,
            "grounding_accuracy": self.grounding_accuracy,
        }


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_run_id: Mapped[int] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    expected_state: Mapped[str] = mapped_column(String(32))
    expected_date_status: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str] = mapped_column(String(32), default="normal")
    failure_case: Mapped[str] = mapped_column(String(64), default="none")
    baseline_explanation: Mapped[str] = mapped_column(Text, default="")
    prototype_explanation: Mapped[str] = mapped_column(Text, default="")
    baseline_understanding: Mapped[float] = mapped_column(Float, default=0.0)
    prototype_understanding: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_followup: Mapped[bool] = mapped_column(Boolean, default=True)
    prototype_followup: Mapped[bool] = mapped_column(Boolean, default=True)
    state_match: Mapped[bool] = mapped_column(Boolean, default=False)
    blocker_match: Mapped[bool] = mapped_column(Boolean, default=False)
    next_action_match: Mapped[bool] = mapped_column(Boolean, default=False)
    date_match: Mapped[bool] = mapped_column(Boolean, default=False)
    grounding_score: Mapped[float] = mapped_column(Float, default=0.0)
    grounding_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    human_understanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_followup: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_run_id": self.experiment_run_id,
            "case_id": self.case_id,
            "ticket_id": self.ticket_id,
            "expected_state": self.expected_state,
            "expected_date_status": self.expected_date_status,
            "difficulty": self.difficulty,
            "failure_case": self.failure_case,
            "baseline_understanding": self.baseline_understanding,
            "prototype_understanding": self.prototype_understanding,
            "baseline_followup": self.baseline_followup,
            "prototype_followup": self.prototype_followup,
            "state_match": self.state_match,
            "blocker_match": self.blocker_match,
            "next_action_match": self.next_action_match,
            "date_match": self.date_match,
            "grounding_score": self.grounding_score,
            "grounding_ok": self.grounding_ok,
            "human_understanding": self.human_understanding,
            "human_followup": self.human_followup,
        }