from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db_session
from app.middleware.roles import get_current_user
from app.models.notification import (
    MarkAllNotificationsReadResponse,
    NotificationResponse,
)


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    unreadOnly: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    where_clause = {"userId": current_user.id}
    if unreadOnly:
        where_clause["isRead"] = False

    notifications = await db.notification.find_many(
        where=where_clause,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    return [NotificationResponse.model_validate(notification) for notification in notifications]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    notification = await db.notification.find_first(
        where={"id": notification_id, "userId": current_user.id}
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    updated_notification = await db.notification.update(
        where={"id": notification_id},
        data={"isRead": True},
    )
    return NotificationResponse.model_validate(updated_notification)


@router.post("/read-all", response_model=MarkAllNotificationsReadResponse)
async def mark_all_notifications_as_read(
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    unread_count = await db.notification.count(
        where={"userId": current_user.id, "isRead": False}
    )
    await db.notification.update_many(
        where={"userId": current_user.id, "isRead": False},
        data={"isRead": True},
    )
    return MarkAllNotificationsReadResponse(updatedCount=unread_count)
