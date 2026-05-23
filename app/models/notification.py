from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    id: int
    userId: int
    type: str
    title: str
    body: str
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="_metadata")
    isRead: bool
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
