import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import ensure_project_access, get_current_user, require_roles
from app.db.database import get_db
from app.models.models import Incident, MonitoringSource, Project, ProjectMembership, User
from app.schemas.schemas import (
    DashboardSummary,
    IncidentRead,
    MonitoringSourceCreate,
    MonitoringSourceRead,
    MonitoringSourceUpdate,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    ProjectUpdate,
)
from app.services.audit import write_audit

router = APIRouter(tags=["projects"])


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Project]:
    query = db.query(Project).filter(Project.is_active.is_(True))
    if user.role == "admin":
        return query.order_by(Project.created_at.desc()).all()

    return (
        query.join(ProjectMembership, ProjectMembership.project_id == Project.project_id)
        .filter(ProjectMembership.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> Project:
    project = Project(
        project_id=new_id("PRJ"),
        name=payload.name,
        description=payload.description,
        environment=payload.environment,
        owner_team=payload.owner_team,
        created_by=user.id,
    )
    db.add(project)
    db.flush()
    db.add(ProjectMembership(project_id=project.project_id, user_id=user.id))
    write_audit(
        db,
        user_id=user.id,
        action="project_created",
        entity_type="project",
        entity_id=project.project_id,
        new_value={"name": project.name},
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    return ensure_project_access(db, user, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> Project:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    old_value = {"name": project.name, "is_active": project.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    write_audit(
        db,
        user_id=user.id,
        action="project_updated",
        entity_type="project",
        entity_id=project.project_id,
        old_value=old_value,
        new_value=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project.is_active = False
    write_audit(
        db,
        user_id=user.id,
        action="project_deactivated",
        entity_type="project",
        entity_id=project.project_id,
    )
    db.commit()
    return {"status": "deactivated", "project_id": project_id}


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectMembership]:
    ensure_project_access(db, user, project_id)
    return (
        db.query(ProjectMembership)
        .options(joinedload(ProjectMembership.user))
        .filter(ProjectMembership.project_id == project_id)
        .order_by(ProjectMembership.created_at.asc())
        .all()
    )


@router.post("/projects/{project_id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: str,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> ProjectMembership:
    ensure_project_access(db, user, project_id)
    target_user = db.query(User).filter(User.id == payload.user_id, User.is_active.is_(True)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    existing = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == payload.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already assigned to this project")

    membership = ProjectMembership(project_id=project_id, user_id=payload.user_id)
    db.add(membership)
    write_audit(
        db,
        user_id=user.id,
        action="project_member_added",
        entity_type="project",
        entity_id=project_id,
        new_value={"user_id": payload.user_id},
    )
    db.commit()
    return (
        db.query(ProjectMembership)
        .options(joinedload(ProjectMembership.user))
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == payload.user_id)
        .one()
    )


@router.delete("/projects/{project_id}/members/{user_id}")
def remove_project_member(
    project_id: str,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    ensure_project_access(db, user, project_id)
    membership = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found")

    db.delete(membership)
    write_audit(
        db,
        user_id=user.id,
        action="project_member_removed",
        entity_type="project",
        entity_id=project_id,
        old_value={"user_id": user_id},
    )
    db.commit()
    return {"status": "removed", "project_id": project_id, "user_id": user_id}


@router.get("/projects/{project_id}/monitoring-sources", response_model=list[MonitoringSourceRead])
def list_monitoring_sources(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MonitoringSource]:
    ensure_project_access(db, user, project_id)
    return (
        db.query(MonitoringSource)
        .filter(MonitoringSource.project_id == project_id)
        .order_by(MonitoringSource.created_at.desc())
        .all()
    )


@router.post(
    "/projects/{project_id}/monitoring-sources",
    response_model=MonitoringSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_monitoring_source(
    project_id: str,
    payload: MonitoringSourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> MonitoringSource:
    ensure_project_access(db, user, project_id)
    token = secrets.token_urlsafe(32)
    webhook_path = f"/alerts/webhook/project/{project_id}/{token}"
    source = MonitoringSource(
        source_id=new_id("SRC"),
        project_id=project_id,
        source_type="prometheus_alertmanager",
        source_name=payload.source_name,
        prometheus_url=payload.prometheus_url,
        alertmanager_url=payload.alertmanager_url,
        dashboard_url=payload.dashboard_url,
        description=payload.description,
        webhook_token=token,
        webhook_path=webhook_path,
        created_by=user.id,
    )
    db.add(source)
    write_audit(
        db,
        user_id=user.id,
        action="monitoring_source_created",
        entity_type="monitoring_source",
        entity_id=source.source_id,
        new_value={"project_id": project_id, "source_type": source.source_type},
    )
    db.commit()
    db.refresh(source)
    return source


@router.get("/projects/{project_id}/monitoring-sources/{source_id}", response_model=MonitoringSourceRead)
def get_monitoring_source(
    project_id: str,
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MonitoringSource:
    ensure_project_access(db, user, project_id)
    source = (
        db.query(MonitoringSource)
        .filter(MonitoringSource.project_id == project_id, MonitoringSource.source_id == source_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring source not found")
    return source


@router.patch("/projects/{project_id}/monitoring-sources/{source_id}", response_model=MonitoringSourceRead)
def update_monitoring_source(
    project_id: str,
    source_id: str,
    payload: MonitoringSourceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> MonitoringSource:
    ensure_project_access(db, user, project_id)
    source = (
        db.query(MonitoringSource)
        .filter(MonitoringSource.project_id == project_id, MonitoringSource.source_id == source_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring source not found")

    old_value = {"source_name": source.source_name, "is_active": source.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    write_audit(
        db,
        user_id=user.id,
        action="monitoring_source_updated",
        entity_type="monitoring_source",
        entity_id=source.source_id,
        old_value=old_value,
        new_value=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(source)
    return source


@router.delete("/projects/{project_id}/monitoring-sources/{source_id}")
def delete_monitoring_source(
    project_id: str,
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    ensure_project_access(db, user, project_id)
    source = (
        db.query(MonitoringSource)
        .filter(MonitoringSource.project_id == project_id, MonitoringSource.source_id == source_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring source not found")
    source.is_active = False
    write_audit(
        db,
        user_id=user.id,
        action="monitoring_source_deactivated",
        entity_type="monitoring_source",
        entity_id=source.source_id,
    )
    db.commit()
    return {"status": "deactivated", "source_id": source_id}


@router.get("/projects/{project_id}/dashboard/summary", response_model=DashboardSummary)
def project_dashboard_summary(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardSummary:
    ensure_project_access(db, user, project_id)
    incidents = db.query(Incident).filter(Incident.project_id == project_id)
    return DashboardSummary(
        project_id=project_id,
        total_incidents=incidents.count(),
        open_incidents=incidents.filter(Incident.status != "resolved").count(),
        critical_incidents=incidents.filter(Incident.severity == "critical").count(),
        resolved_incidents=incidents.filter(Incident.status == "resolved").count(),
    )


@router.get("/projects/{project_id}/incidents", response_model=list[IncidentRead])
def list_project_incidents(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Incident]:
    ensure_project_access(db, user, project_id)
    return (
        db.query(Incident)
        .filter(Incident.project_id == project_id)
        .order_by(Incident.created_at.desc())
        .limit(200)
        .all()
    )


@router.get("/projects/{project_id}/incidents/{incident_id}", response_model=IncidentRead)
def get_project_incident(
    project_id: str,
    incident_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Incident:
    ensure_project_access(db, user, project_id)
    incident = (
        db.query(Incident)
        .filter(Incident.project_id == project_id, Incident.incident_id == incident_id)
        .first()
    )
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident
