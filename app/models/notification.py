from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    userId: int
    type: str
    title: str
    body: str
    metadata: Optional[Dict[str, Any]] = None
    isRead: bool
    createdAt: datetime

    class Config:
        from_attributes = True
