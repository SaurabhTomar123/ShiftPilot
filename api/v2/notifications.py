"""The in-app inbox (architecture v3 section 40): deliveries written by jobs.outbox_relay."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from api.v2 import schemas as s
from api.v2.errors import not_found
from core.auth import Caller
from db.models import Outlet
from db.models_v2 import NotificationDelivery
from db.session import tenant_session

LIMIT = 100


def _view(n: NotificationDelivery, tz: ZoneInfo) -> s.Notification:
    return s.Notification(
        id=n.id,
        topic=n.topic,
        title=n.title,
        payload=n.payload,
        delivered_at=n.delivered_at.astimezone(tz),
        read_at=n.read_at.astimezone(tz) if n.read_at else None,
    )


def _tz(caller: Caller, session: object) -> ZoneInfo:
    outlet = session.get(Outlet, uuid.UUID(caller.outlet_id)) if caller.outlet_id else None  # type: ignore[attr-defined]
    return ZoneInfo(outlet.timezone if outlet else "Asia/Kolkata")


def inbox(caller: Caller, unread_only: bool) -> s.NotificationList:
    with tenant_session(caller) as session:
        query = (
            select(NotificationDelivery)
            .where(NotificationDelivery.recipient_user_id == uuid.UUID(caller.user_id))
            .order_by(NotificationDelivery.delivered_at.desc(), NotificationDelivery.id.desc())
            .limit(LIMIT)
        )
        if unread_only:
            query = query.where(NotificationDelivery.read_at.is_(None))
        tz = _tz(caller, session)
        return s.NotificationList(items=[_view(n, tz) for n in session.scalars(query)])


def mark_read(caller: Caller, notification_id: uuid.UUID) -> s.Notification:
    with tenant_session(caller) as session:
        n = session.get(NotificationDelivery, notification_id)
        if n is None or n.recipient_user_id != uuid.UUID(caller.user_id):
            raise not_found("Notification")
        if n.read_at is None:
            n.read_at = datetime.now(UTC)
            session.flush()
        return _view(n, _tz(caller, session))
