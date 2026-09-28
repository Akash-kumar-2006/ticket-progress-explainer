from datetime import datetime

from pydantic import BaseModel, Field


class EventData(BaseModel):
    """Normalized in-memory representation of a ticket event."""

    event_id: str
    ticket_id: str
    timestamp: datetime
    event_type: str
    actor_type: str = "AGENT"
    actor_id: str = ""
    region: str = ""
    team: str = ""
    old_status: str | None = None
    new_status: str | None = None
    message: str = ""
    dependency_id: str | None = None
    dependency_title: str | None = None
    dependency_owner: str | None = None
    vendor: str | None = None
    vendor_item: str | None = None
    approval_type: str | None = None
    promised_date: datetime | None = None
    is_duplicate: bool = False
    is_out_of_order: bool = False
    conflict_flag: bool = False
    metadata: dict = Field(default_factory=dict)

    def label(self) -> str:
        """Short human readable description used on the timeline."""
        msg = self.message or ""
        return f"{self.event_type}: {msg}" if msg else self.event_type


class TimelineEntry(BaseModel):
    index: int
    event_id: str
    timestamp: datetime
    event_type: str
    title: str
    description: str
    region: str
    team: str
    actor: str
    flags: list[str] = []


class Timeline(BaseModel):
    ticket_id: str
    entries: list[TimelineEntry] = []
    duplicates: list[str] = []
    out_of_order: list[str] = []
    conflicts: list[str] = []
    total: int = 0


class DependencyInfo(BaseModel):
    dependency_id: str
    title: str
    kind: str  # approval | vendor | internal | customer | action | other
    status: str  # pending | completed | blocked
    owner: str
    created_at: datetime
    completed_at: datetime | None = None
    age_days: float | None = None
    source_event_id: str
    latest_update_at: datetime | None = None
    latest_update_message: str = ""


class DateAnalysis(BaseModel):
    date_status: str | None  # ON_TRACK | AT_RISK | OVERDUE | COMPLETED | None
    risk: str
    days_remaining: int | None
    overdue_days: int = 0
    delay_evidence_ids: list[str] = []
    reasons: list[str] = []


class ProgressResult(BaseModel):
    ticket_id: str
    progress_state: str
    effective_status: str
    date_status: str | None
    risk: str
    days_remaining: int | None
    overdue_days: int = 0
    promised_date: datetime | None = None
    next_action: str | None = None
    next_action_evidence: list[str] = []
    #: Lexicon category of next_action (e.g. APPROVAL, VENDOR_RESPONSE) or "".
    next_action_category: str = ""
    #: specific | generic | sparse
    next_action_confidence: str = ""
    reasons: list[str] = []
    evidence_ids: list[str] = []
    blockers: list[str] = []
    waiting_on: str | None = None


class EvidenceItem(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    text: str
    reason: str
    conflict_flag: bool = False


class Claim(BaseModel):
    category: str
    text: str
    evidence: list[str] = []
    supported: bool = True


class ExplanationPayload(BaseModel):
    ticket_id: str
    progress_state: str
    effective_status: str
    date_status: str | None
    risk: str
    grounding_score: int
    grounding_breakdown: list[str] = []
    explanation: str = ""
    claims: list[Claim] = []
    evidence: list[EvidenceItem] = []
    next_action: str | None = None
    next_action_evidence: list[str] = []
    next_action_category: str = ""
    next_action_confidence: str = ""
    promised_date: datetime | None = None
    days_remaining: int | None = None
    insufficient_evidence: bool = False
    conflicts: list[str] = []
    model_version: str = ""
    rules_version: str = ""
    is_baseline: bool = False

    def to_api(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "progress_state": self.progress_state,
            "effective_status": self.effective_status,
            "date_status": self.date_status,
            "risk": self.risk,
            "grounding_score": self.grounding_score,
            "grounding_breakdown": self.grounding_breakdown,
            "explanation": self.explanation,
            "claims": [c.model_dump() for c in self.claims],
            "evidence": [
                {"event_id": e.event_id, "type": e.event_type, "reason": e.reason, "text": e.text}
                for e in self.evidence
            ],
            "next_action": self.next_action,
            "next_action_evidence": self.next_action_evidence,
            "next_action_category": self.next_action_category,
            "next_action_confidence": self.next_action_confidence,
            "promised_date": self.promised_date.isoformat() if self.promised_date else None,
            "days_remaining": self.days_remaining,
            "insufficient_evidence": self.insufficient_evidence,
            "conflicts": self.conflicts,
            "model_version": self.model_version,
            "rules_version": self.rules_version,
            "is_baseline": self.is_baseline,
        }