from typing import Any

from pydantic import BaseModel, Field


class EventImport(BaseModel):
    event_id: str
    ticket_id: str
    timestamp: str
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
    promised_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportRequest(BaseModel):
    source: str = "manual"
    tickets: list[dict] = Field(default_factory=list)
    events: list[EventImport] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    actor: str = "reviewer"
    role: str = "REVIEWER"
    decision: str  # APPROVE | REJECT
    reason: str = ""


class PublishRequest(BaseModel):
    actor: str = "support_agent"
    role: str = "REVIEWER"


class RollbackRequest(BaseModel):
    actor: str = "admin"
    role: str = "ADMIN"
    reason: str = ""
    target_version: int | None = None


class EvaluationRunRequest(BaseModel):
    as_of: str | None = None


class TicketCreate(BaseModel):
    ticket_id: str
    customer_reference: str
    subject: str
    category: str
    priority: str
    region: str
    current_team: str
    current_status: str
    created_at: str
    updated_at: str
    promised_date: str | None = None
    actual_resolution_date: str | None = None
    sla_status: str = "ACTIVE"