from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


class UserLogin(BaseModel):
    """User login request model."""
    email: Optional[EmailStr] = None
    phone: Optional[int] = None
    password: str = Field(..., min_length=6)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123"
            }
        }


class StaffLogin(BaseModel):
    """Staff login with phone number (for 2FA flow)"""
    phone: int = Field(..., description="Staff phone number")
    password: str = Field(..., min_length=6, description="Staff password")


class TempTokenResponse(BaseModel):
    """Temporary token response for 2FA"""
    tempToken: str
    message: str
    requiresOtp: bool = True
    expiresIn: int = Field(default=300, description="Temp token expires in seconds (5 minutes)")


class OtpVerificationRequest(BaseModel):
    """OTP verification with temporary token"""
    tempToken: str = Field(..., description="Temporary token from login")
    otpCode: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class UserRegister(BaseModel):
    """User registration request model."""
    email: Optional[EmailStr] = None
    phone: int
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.CLIENT
    restaurantId: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "phone": 1234567890,
                "firstName": "John",
                "lastName": "Doe",
                "password": "securepassword123",
                "role": "CLIENT"
            }
        }


class UserResponse(BaseModel):
    """User response model."""
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


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str


class PasswordChange(BaseModel):
    """Password change request model."""
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """User update request model."""
    email: Optional[EmailStr] = None
    firstName: Optional[str] = Field(None, min_length=1, max_length=100)
    lastName: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[int] = None
    role: Optional[UserRole] = None
    isActive: Optional[bool] = None
    restaurantId: Optional[int] = None
