import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_notification_event(event_type: str, payload: dict[str, Any]) -> None:
    if not settings.enable_notifications:
        return

    url = f"{settings.notification_service_url.rstrip('/')}/notifications/events"
    body = {"event_type": event_type, "payload": payload}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=body)
    except Exception as exc:
        logger.warning("Notification event delivery failed: %s", exc.__class__.__name__)
