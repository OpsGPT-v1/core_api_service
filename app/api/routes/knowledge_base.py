from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import ensure_project_access, get_current_user, require_roles
from app.db.database import get_db
from app.models.models import KnowledgeBase, ProjectMembership, User
from app.schemas.schemas import KnowledgeBaseCreate, KnowledgeBaseRead
from app.services.audit import write_audit

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_base(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KnowledgeBase]:
    query = db.query(KnowledgeBase)
    if user.role != "admin":
        project_ids = select(ProjectMembership.project_id).where(ProjectMembership.user_id == user.id)
        query = query.filter(or_(KnowledgeBase.project_id.is_(None), KnowledgeBase.project_id.in_(project_ids)))
    return query.order_by(KnowledgeBase.updated_at.desc()).limit(100).all()


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base_item(
    kb_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeBase:
    item = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base item not found")
    if item.project_id:
        ensure_project_access(db, user, item.project_id)
    return item


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base_item(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("senior_engineer", "admin")),
) -> KnowledgeBase:
    if payload.project_id:
        ensure_project_access(db, user, payload.project_id)
    item = KnowledgeBase(**payload.model_dump())
    db.add(item)
    db.flush()
    write_audit(
        db,
        user_id=user.id,
        action="knowledge_base_created",
        entity_type="knowledge_base",
        entity_id=str(item.id),
        new_value={"title": item.title},
    )
    db.commit()
    db.refresh(item)
    return item
