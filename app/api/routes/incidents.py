from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import ensure_project_access, get_current_user, require_roles
from app.db.database import get_db
from app.models.models import Incident, IncidentTimeline, ProjectMembership, ResolutionNote, User
from app.schemas.schemas import IncidentRead, IncidentStatusUpdate, ResolutionNoteCreate, ResolutionNoteRead, TimelineRead
from app.services.audit import write_audit
from app.services.notifications import send_notification_event

router = APIRouter(prefix="/incidents", tags=["incidents"])


def incident_query_for_user(db: Session, user: User):
    query = db.query(Incident)
    if user.role == "admin":
        return query
    project_ids = select(ProjectMembership.project_id).where(ProjectMembership.user_id == user.id)
    return query.filter(Incident.project_id.in_(project_ids))


def get_visible_incident(db: Session, user: User, incident_id: str) -> Incident:
    incident = incident_query_for_user(db, user).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Incident]:
    return incident_query_for_user(db, user).order_by(Incident.created_at.desc()).limit(200).all()


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Incident:
    return get_visible_incident(db, user, incident_id)


@router.patch("/{incident_id}/status", response_model=IncidentRead)
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("senior_engineer", "admin")),
) -> Incident:
    incident = get_visible_incident(db, user, incident_id)
    if incident.project_id:
        ensure_project_access(db, user, incident.project_id)

    old_status = incident.status
    incident.status = payload.status
    if payload.status == "resolved":
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolved_by = user.id
    db.add(
        IncidentTimeline(
            incident_id=incident.incident_id,
            event_type="incident_status_updated",
            message=f"Status changed from {old_status} to {payload.status}",
            created_by=user.id,
        )
    )
    write_audit(
        db,
        user_id=user.id,
        action="incident_status_updated",
        entity_type="incident",
        entity_id=incident.incident_id,
        old_value={"status": old_status},
        new_value={"status": payload.status},
    )
    db.commit()
    db.refresh(incident)
    await send_notification_event(
        "incident_resolved" if payload.status == "resolved" else "incident_status_updated",
        {
            "incident_id": incident.incident_id,
            "project_id": incident.project_id,
            "service_name": incident.service_name,
            "severity": incident.severity,
            "status": incident.status,
        },
    )
    return incident


@router.post("/{incident_id}/resolution-notes", response_model=ResolutionNoteRead, status_code=status.HTTP_201_CREATED)
async def add_resolution_note(
    incident_id: str,
    payload: ResolutionNoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("senior_engineer", "admin")),
) -> ResolutionNote:
    incident = get_visible_incident(db, user, incident_id)
    note = ResolutionNote(incident_id=incident.incident_id, notes=payload.notes, created_by=user.id)
    db.add(note)
    db.add(
        IncidentTimeline(
            incident_id=incident.incident_id,
            event_type="resolution_notes_added",
            message="Resolution notes added",
            created_by=user.id,
        )
    )
    write_audit(
        db,
        user_id=user.id,
        action="resolution_notes_added",
        entity_type="incident",
        entity_id=incident.incident_id,
    )
    db.commit()
    db.refresh(note)
    await send_notification_event(
        "resolution_notes_added",
        {"incident_id": incident.incident_id, "project_id": incident.project_id, "service_name": incident.service_name},
    )
    return note


@router.get("/{incident_id}/timeline", response_model=list[TimelineRead])
def get_incident_timeline(
    incident_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[IncidentTimeline]:
    incident = get_visible_incident(db, user, incident_id)
    return (
        db.query(IncidentTimeline)
        .filter(IncidentTimeline.incident_id == incident.incident_id)
        .order_by(IncidentTimeline.created_at.asc())
        .all()
    )


@router.get("/{incident_id}/similar", response_model=list[IncidentRead])
def get_similar_incidents(
    incident_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Incident]:
    incident = get_visible_incident(db, user, incident_id)
    return (
        incident_query_for_user(db, user)
        .filter(Incident.incident_id != incident.incident_id, Incident.service_name == incident.service_name)
        .order_by(Incident.created_at.desc())
        .limit(10)
        .all()
    )
