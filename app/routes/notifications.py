from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.middleware.roles import get_current_user
from app.models.notification import NotificationResponse
from app.models.sqlalchemy_models import Notification, User
from app.utils.logging import logger

router = APIRouter(prefix="/notifications", tags=["Notifications"])


async def create_restaurant_event_notifications(
    db: AsyncSession,
    restaurant_id: int,
    notification_type: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
):
    """Create manager/admin notifications for a restaurant-scoped event."""

    try:
        result = await db.execute(
            select(User).where(
                and_(
                    User.isActive == True,
                    or_(
                        User.role == "ADMIN",
                        and_(User.role == "MANAGER", User.restaurantId == restaurant_id),
                    ),
                )
            )
        )
        recipients = result.scalars().all()

        for recipient in recipients:
            notification = Notification(
                userId=recipient.id,
                type=notification_type,
                title=title,
                body=body,
                _metadata=metadata,
            )
            db.add(notification)

        await db.commit()
    except Exception as exc:
        logger.error("Failed to create notifications for restaurant {}: {}", restaurant_id, exc)


@router.get("/", response_model=list[NotificationResponse])
async def get_notifications(
    unreadOnly: bool = Query(False),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get notifications for the current user."""

    stmt = select(Notification).where(Notification.userId == current_user.id)
    if unreadOnly:
        stmt = stmt.where(Notification.isRead == False)
    stmt = stmt.order_by(Notification.createdAt.desc())

    result = await db.execute(stmt)
    notifications = result.scalars().all()

    return [NotificationResponse.model_validate(n) for n in notifications]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Mark a single notification as read."""

    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    if not notification or notification.userId != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.isRead = True
    await db.commit()
    await db.refresh(notification)

    return NotificationResponse.model_validate(notification)


@router.post("/read-all")
async def mark_all_notifications_as_read(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Mark all notifications for the current user as read."""

    result = await db.execute(
        select(Notification).where(
            Notification.userId == current_user.id,
            Notification.isRead == False,
        )
    )
    unread = result.scalars().all()
    unread_count = len(unread)

    if unread_count:
        for n in unread:
            n.isRead = True
        await db.commit()

    return {
        "message": "Notifications marked as read",
        "updatedCount": unread_count,
    }
