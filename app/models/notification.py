from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    id: int
    userId: int
    type: str
    title: str
    body: str
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="_metadata")
    isRead: bool
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
