from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class OtpPurpose(str, Enum):
    STAFF_AUTH = "STAFF_AUTH"
    PAYMENT_CONFIRMATION = "PAYMENT_CONFIRMATION"
    PASSWORD_RESET = "PASSWORD_RESET"


class OtpSendRequest(BaseModel):
    phone: int = Field(..., description="Phone number to send OTP to")
    purpose: OtpPurpose = Field(default=OtpPurpose.STAFF_AUTH, description="Purpose of OTP")


class OtpSendResponse(BaseModel):
    success: bool
    message: str
    expiresIn: int = Field(default=1200, description="OTP expires in seconds (20 minutes)")


class OtpVerifyRequest(BaseModel):
    phone: int = Field(..., description="Phone number")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    purpose: OtpPurpose = Field(default=OtpPurpose.STAFF_AUTH, description="Purpose of OTP")


class OtpVerifyResponse(BaseModel):
    success: bool
    message: str
    accessToken: Optional[str] = None
    user: Optional[dict] = None


class PaymentOtpRequest(BaseModel):
    orderId: int = Field(..., description="Order ID to confirm payment for")


class PaymentOtpVerifyRequest(BaseModel):
    orderId: int = Field(..., description="Order ID")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class StaffLoginRequest(BaseModel):
    phone: int = Field(..., description="Staff phone number")


class StaffOtpVerifyRequest(BaseModel):
    phone: int = Field(..., description="Staff phone number")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
