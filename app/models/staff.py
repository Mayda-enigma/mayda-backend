from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class StaffResponse(BaseModel):
    id: int
    email: Optional[str]
    phone: int
    firstName: str
    lastName: str
    role: UserRole
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    restaurantId: Optional[int]

    class Config:
        from_attributes = True


class StaffListResponse(BaseModel):
    restaurantId: int
    restaurantName: str
    staff: list[StaffResponse]
    totalStaff: int


class StaffInviteRequest(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    phone: int
    email: Optional[EmailStr] = None
    role: UserRole


class StaffInviteResponse(BaseModel):
    message: str
    smsSent: bool
    staff: StaffResponse


class StaffUpdate(BaseModel):
    role: Optional[UserRole] = None
    isActive: Optional[bool] = None
