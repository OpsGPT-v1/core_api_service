from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.core.security import hash_password
from app.db.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserRead, UserRoleUpdate
from app.services.audit import write_audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def users_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[User]:
    return db.query(User).order_by(User.name.asc()).all()


@router.get("/search", response_model=list[UserRead])
def search_users(
    query: str = Query(default=""),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[User]:
    term = f"%{query.strip()}%"
    return (
        db.query(User)
        .filter(or_(User.name.ilike(term), User.email.ilike(term), User.role.ilike(term)))
        .order_by(User.name.asc())
        .limit(20)
        .all()
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User email already exists")

    new_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    write_audit(
        db,
        user_id=user.id,
        action="user_created",
        entity_type="user",
        entity_id=str(new_user.id),
        new_value={"email": new_user.email, "role": new_user.role},
    )
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = target.role
    target.role = payload.role
    write_audit(
        db,
        user_id=user.id,
        action="user_role_updated",
        entity_type="user",
        entity_id=str(target.id),
        old_value={"role": old_role},
        new_value={"role": target.role},
    )
    db.commit()
    db.refresh(target)
    return target
