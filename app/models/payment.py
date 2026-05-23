from datetime import datetime

from pydantic import BaseModel

from app.core.config import settings

# Guidini Pay API Configuration
GUIDINI_PAY_URL = "https://epay.guiddini.dz/api/payment/initiate"
GUIDINI_PAY_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-app-key": settings.GUIDINI_APP_KEY,
    "x-app-secret": settings.GUIDINI_API_KEY,
}


class PaymentCreate(BaseModel):
    orderId: int


class PaymentResponse(BaseModel):
    id: int
    paymentId: str  # Guidini Pay transaction ID
    orderId: int
    order: dict | None = None  # Order details
    createdAt: datetime

    class Config:
        from_attributes = True


class PaymentInitiateRequest(BaseModel):
    orderId: int
    language: str


class PaymentInitiateResponse(BaseModel):
    success: bool
    paymentId: str | None = None  # Internal payment record ID
    transactionId: str | None = None  # Guidini Pay transaction ID
    formUrl: str | None = None  # Payment form URL
    amount: str | None = None
    message: str
    error: str | None = None


class PaymentStatusResponse(BaseModel):
    id: int
    paymentId: str
    orderId: int
    orderNumber: str | None = None
    amount: float
    status: str  # From order.paymentStatus
    createdAt: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    payments: list[PaymentStatusResponse]
    total: int
    page: int
    pageSize: int
