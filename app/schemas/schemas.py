from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["junior_engineer", "senior_engineer", "admin"]
Severity = Literal["critical", "warning", "informational"]
IncidentStatus = Literal["open", "investigating", "mitigated", "resolved"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role


class UserRoleUpdate(BaseModel):
    role: Role


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    environment: str = "production"
    owner_team: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    environment: str | None = None
    owner_team: str | None = None
    is_active: bool | None = None


class ProjectRead(BaseModel):
    id: int
    project_id: str
    name: str
    description: str | None
    environment: str
    owner_team: str | None
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectMemberCreate(BaseModel):
    user_id: int


class ProjectMemberRead(BaseModel):
    id: int
    project_id: str
    user_id: int
    created_at: datetime
    user: UserRead

    model_config = ConfigDict(from_attributes=True)


class MonitoringSourceCreate(BaseModel):
    source_type: Literal["prometheus_alertmanager"] = "prometheus_alertmanager"
    source_name: str
    prometheus_url: str | None = None
    alertmanager_url: str | None = None
    dashboard_url: str | None = None
    description: str | None = None


class MonitoringSourceUpdate(BaseModel):
    source_name: str | None = None
    prometheus_url: str | None = None
    alertmanager_url: str | None = None
    dashboard_url: str | None = None
    description: str | None = None
    is_active: bool | None = None


class MonitoringSourceRead(BaseModel):
    id: int
    source_id: str
    project_id: str
    source_type: str
    source_name: str
    prometheus_url: str | None
    alertmanager_url: str | None
    dashboard_url: str | None
    description: str | None
    webhook_token: str
    webhook_path: str
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentRead(BaseModel):
    id: int
    incident_id: str
    project_id: str | None
    title: str
    service_name: str
    severity: str
    status: str
    ai_summary: str | None
    root_cause: str | None
    supporting_evidence: list[Any] | None
    confidence_score: float | None
    recommended_fix: dict[str, Any] | None
    related_alert_ids: list[Any]
    source_type: str
    namespace: str | None
    cluster: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolved_by: int | None

    model_config = ConfigDict(from_attributes=True)


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class ResolutionNoteCreate(BaseModel):
    notes: str


class ResolutionNoteRead(BaseModel):
    id: int
    incident_id: str
    notes: str
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineCreate(BaseModel):
    event_type: str
    message: str
    created_by: int | None = None


class TimelineRead(BaseModel):
    id: int
    incident_id: str
    event_type: str
    message: str
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    project_id: str
    total_incidents: int
    open_incidents: int
    critical_incidents: int
    resolved_incidents: int


class KnowledgeBaseCreate(BaseModel):
    title: str
    project_id: str | None = None
    service_name: str
    root_cause: str
    summary: str
    resolution_steps: list[str] = Field(default_factory=list)
    source_incident_id: str | None = None


class KnowledgeBaseRead(KnowledgeBaseCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogRead(BaseModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InternalIncidentCreate(BaseModel):
    incident_id: str | None = None
    project_id: str | None = None
    title: str
    service_name: str
    severity: Severity
    status: IncidentStatus = "open"
    related_alert_ids: list[str]
    source_type: Literal["prometheus_alertmanager"] = "prometheus_alertmanager"
    namespace: str | None = None
    cluster: str | None = None


class InternalAnalysisUpdate(BaseModel):
    ai_summary: str | None = None
    root_cause: str | None = None
    supporting_evidence: list[Any] | None = None
    confidence_score: float | None = None
    recommended_fix: dict[str, Any] | None = None
