import logging

from sqlalchemy import func

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.models import User

logger = logging.getLogger(__name__)

DEFAULT_USERS = [
    {
        "name": "Junior Engineer",
        "email": "junior.engineer@company.com",
        "password": "password123",
        "role": "junior_engineer",
    },
    {
        "name": "Senior Engineer",
        "email": "senior.engineer@company.com",
        "password": "password123",
        "role": "senior_engineer",
    },
    {"name": "Admin", "email": "admin@company.com", "password": "password123", "role": "admin"},
]


def seed_default_users() -> int:
    db = SessionLocal()
    try:
        seeded_count = 0
        for item in DEFAULT_USERS:
            email = item["email"].lower()
            existing = db.query(User).filter(func.lower(User.email) == email).first()
            if existing:
                existing.name = item["name"]
                existing.email = email
                existing.password_hash = hash_password(item["password"])
                existing.role = item["role"]
                existing.is_active = True
                seeded_count += 1
                continue
            db.add(
                User(
                    name=item["name"],
                    email=email,
                    password_hash=hash_password(item["password"]),
                    role=item["role"],
                    is_active=True,
                )
            )
            seeded_count += 1
        db.commit()
        logger.info("Core API default users are present: %s", seeded_count)
        return seeded_count
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to seed default users: %s", exc.__class__.__name__)
        raise
    finally:
        db.close()
