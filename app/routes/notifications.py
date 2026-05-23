from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Json

from app.core.database import get_db_session
from app.middleware.roles import get_current_user
from app.models.notification import NotificationResponse
from app.utils.logging import logger


router = APIRouter(prefix="/notifications", tags=["Notifications"])


async def create_restaurant_event_notifications(
    db: "Prisma",
    restaurant_id: int,
    notification_type: str,
    title: str,
    body: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Create manager/admin notifications for a restaurant-scoped event."""

    try:
        recipients = await db.user.find_many(
            where={
                "isActive": True,
                "OR": [
                    {"role": "ADMIN"},
                    {"role": "MANAGER", "restaurantId": restaurant_id},
                ],
            }
        )

        for recipient in recipients:
            await db.notification.create(
                data={
                    "user": {"connect": {"id": recipient.id}},
                    "type": notification_type,
                    "title": title,
                    "body": body,
                    "metadata": Json(metadata) if metadata is not None else None,
                }
            )
    except Exception as exc:
        logger.error("Failed to create notifications for restaurant {}: {}", restaurant_id, exc)


@router.get("/", response_model=list[NotificationResponse])
async def get_notifications(
    unreadOnly: bool = Query(False),
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get notifications for the current user."""

    where_clause = {"userId": current_user.id}
    if unreadOnly:
        where_clause["isRead"] = False

    notifications = await db.notification.find_many(
        where=where_clause,
        order={"createdAt": "desc"},
    )

    return [NotificationResponse.model_validate(notification) for notification in notifications]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Mark a single notification as read."""

    notification = await db.notification.find_unique(where={"id": notification_id})
    if not notification or notification.userId != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    updated_notification = await db.notification.update(
        where={"id": notification_id},
        data={"isRead": True},
    )

    return NotificationResponse.model_validate(updated_notification)


@router.post("/read-all")
async def mark_all_notifications_as_read(
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Mark all notifications for the current user as read."""

    unread_count = await db.notification.count(
        where={"userId": current_user.id, "isRead": False}
    )

    if unread_count:
        await db.notification.update_many(
            where={"userId": current_user.id, "isRead": False},
            data={"isRead": True},
        )

    return {
        "message": "Notifications marked as read",
        "updatedCount": unread_count,
    }
