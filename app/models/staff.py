from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from app.models.user import UserRole


class StaffInviteRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: int
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    role: UserRole


class StaffUpdateRequest(BaseModel):
    role: Optional[UserRole] = None
    isActive: Optional[bool] = None
