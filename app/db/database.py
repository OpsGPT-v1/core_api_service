import logging
import time
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> bool:
    from app.models import models  # noqa: F401

    for attempt in range(1, settings.db_init_max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Core API database tables are ready")
            return True
        except SQLAlchemyError as exc:
            logger.warning("Core API database not ready, attempt %s: %s", attempt, exc.__class__.__name__)
            time.sleep(settings.db_init_delay_seconds)

    logger.error("Core API database initialization did not complete")
    return False
