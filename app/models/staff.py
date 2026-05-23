from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class StaffResponse(BaseModel):
    id: int
    email: str | None
    phone: int
    firstName: str
    lastName: str
    role: UserRole
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    restaurantId: int | None

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
    email: EmailStr | None = None
    role: UserRole


class StaffInviteResponse(BaseModel):
    message: str
    smsSent: bool
    staff: StaffResponse


class StaffUpdate(BaseModel):
    role: UserRole | None = None
    isActive: bool | None = None
