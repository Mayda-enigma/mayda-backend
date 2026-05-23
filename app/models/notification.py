from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class NotificationType(str, Enum):
    ORDER_PLACED = "order_placed"
    LOW_STOCK = "low_stock"
    RESERVATION = "reservation"


class NotificationResponse(BaseModel):
    id: int
    userId: int
    type: NotificationType
    title: str
    body: str
    metadata: Optional[dict] = None
    isRead: bool
    createdAt: datetime

    class Config:
        from_attributes = True


class MarkAllNotificationsReadResponse(BaseModel):
    updatedCount: int
