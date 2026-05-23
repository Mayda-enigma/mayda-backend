from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles enum matching Prisma schema."""

    CLIENT = "CLIENT"
    WAITER = "WAITER"
    CHEF = "CHEF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class PushTokenPlatform(str, Enum):
    """Supported mobile push platforms."""

    IOS = "ios"
    ANDROID = "android"


class PushTokenUpsertRequest(BaseModel):
    """Push token registration request model."""

    token: str = Field(..., min_length=1)
    platform: PushTokenPlatform


class PushTokenResponse(BaseModel):
    """Push token response model."""

    id: int
    userId: int
    token: str
    platform: PushTokenPlatform
    createdAt: datetime

    class Config:
        from_attributes = True
