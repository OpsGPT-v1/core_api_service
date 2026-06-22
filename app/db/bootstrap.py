import logging
import sys

from app.db.database import init_db
from app.db.seed import seed_default_users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("Starting Core API database bootstrap")
    if not init_db():
        logger.error("Core API database bootstrap failed during table creation")
        return 1

    try:
        seed_default_users()
    except Exception:
        logger.exception("Core API database bootstrap failed during default user seeding")
        return 1

    logger.info("Core API database bootstrap completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
