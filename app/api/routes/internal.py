import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_internal_api_key
from app.db.database import get_db
from app.models.models import Incident, IncidentTimeline, MonitoringSource
from app.schemas.schemas import InternalAnalysisUpdate, InternalIncidentCreate, IncidentRead, TimelineCreate, TimelineRead
from app.services.notifications import send_notification_event

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_api_key)])


def generated_incident_id() -> str:
    return f"INC-{uuid.uuid4().hex[:12].upper()}"


@router.post("/incidents", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_internal_incident(
    payload: InternalIncidentCreate,
    db: Session = Depends(get_db),
) -> Incident:
    incident_id = payload.incident_id or generated_incident_id()
    existing = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if existing:
        return existing

    incident = Incident(
        incident_id=incident_id,
        project_id=payload.project_id,
        title=payload.title,
        service_name=payload.service_name,
        severity=payload.severity,
        status=payload.status,
        related_alert_ids=payload.related_alert_ids,
        source_type=payload.source_type,
        namespace=payload.namespace,
        cluster=payload.cluster,
    )
    db.add(incident)
    db.add(
        IncidentTimeline(
            incident_id=incident_id,
            event_type="incident_created",
            message=f"Incident created from {len(payload.related_alert_ids)} alert(s)",
        )
    )
    db.commit()
    db.refresh(incident)
    await send_notification_event(
        "incident_created",
        {
            "incident_id": incident.incident_id,
            "project_id": incident.project_id,
            "service_name": incident.service_name,
            "severity": incident.severity,
            "status": incident.status,
        },
    )
    return incident


@router.patch("/incidents/{incident_id}/analysis", response_model=IncidentRead)
async def update_incident_analysis(
    incident_id: str,
    payload: InternalAnalysisUpdate,
    db: Session = Depends(get_db),
) -> Incident:
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(incident, field, value)
    db.add(
        IncidentTimeline(
            incident_id=incident.incident_id,
            event_type="ai_analysis_completed",
            message="AI analysis fields updated",
        )
    )
    db.commit()
    db.refresh(incident)
    await send_notification_event(
        "ai_analysis_completed",
        {
            "incident_id": incident.incident_id,
            "project_id": incident.project_id,
            "service_name": incident.service_name,
            "severity": incident.severity,
            "root_cause": incident.root_cause,
        },
    )
    return incident


@router.post("/incidents/{incident_id}/timeline", response_model=TimelineRead, status_code=status.HTTP_201_CREATED)
def add_internal_timeline_event(
    incident_id: str,
    payload: TimelineCreate,
    db: Session = Depends(get_db),
) -> IncidentTimeline:
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    event = IncidentTimeline(
        incident_id=incident_id,
        event_type=payload.event_type,
        message=payload.message,
        created_by=payload.created_by,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/projects/{project_id}/monitoring-sources/validate")
def validate_monitoring_source(
    project_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    source = (
        db.query(MonitoringSource)
        .filter(
            MonitoringSource.project_id == project_id,
            MonitoringSource.webhook_token == token,
            MonitoringSource.is_active.is_(True),
            MonitoringSource.source_type == "prometheus_alertmanager",
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid project webhook token")

    return {
        "valid": True,
        "project_id": source.project_id,
        "source_id": source.source_id,
        "source_type": source.source_type,
        "source_name": source.source_name,
    }
