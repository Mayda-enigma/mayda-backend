from datetime import datetime
from enum import Enum

from pydantic import BaseModel, validator


class ReservationStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class ReservationCreate(BaseModel):
    restaurantId: int
    tableId: int | None = None
    reservationStart: datetime
    reservationEnd: datetime
    # Note: No customer info needed - uses authenticated user's profile automatically
    specialRequests: str | None = None  # Any special requests for the reservation
    partySize: int | None = None  # Number of people (helps with table selection)

    @validator("reservationEnd")
    def validate_end_time(cls, v, values):
        if "reservationStart" in values and v <= values["reservationStart"]:
            raise ValueError("Reservation end time must be after start time")
        return v

    @validator("reservationStart")
    def validate_start_time(cls, v):
        if v <= datetime.now():
            raise ValueError("Reservation start time must be in the future")
        return v


class PublicReservationCreate(BaseModel):
    """For staff creating reservations on behalf of customers (phone bookings, walk-ins)."""

    restaurantId: int
    tableId: int | None = None
    reservationStart: datetime
    reservationEnd: datetime
    customerName: str
    customerPhone: str
    customerEmail: str | None = None
    partySize: int | None = None
    specialRequests: str | None = None

    @validator("reservationEnd")
    def validate_end_time(cls, v, values):
        if "reservationStart" in values and v <= values["reservationStart"]:
            raise ValueError("Reservation end time must be after start time")
        return v

    @validator("reservationStart")
    def validate_start_time(cls, v):
        if v <= datetime.now():
            raise ValueError("Reservation start time must be in the future")
        return v


class ReservationUpdate(BaseModel):
    tableId: int | None = None
    reservationStart: datetime | None = None
    reservationEnd: datetime | None = None

    @validator("reservationEnd")
    def validate_end_time(cls, v, values):
        if v and "reservationStart" in values and values["reservationStart"] and v <= values["reservationStart"]:
            raise ValueError("Reservation end time must be after start time")
        return v


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationResponse(BaseModel):
    id: int
    userId: int | None
    user: dict | None = None
    tableId: int | None
    table: dict | None = None
    restaurantId: int
    restaurant: dict | None = None
    reservationStart: datetime
    reservationEnd: datetime
    status: ReservationStatus
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class ReservationListResponse(BaseModel):
    id: int
    userId: int | None
    customerName: str | None = None
    customerPhone: str | None = None
    tableId: int | None
    tableNumber: str | None = None
    restaurantId: int
    restaurantName: str | None = None
    reservationStart: datetime
    reservationEnd: datetime
    status: ReservationStatus
    createdAt: datetime

    class Config:
        from_attributes = True


class ReservationAvailabilityRequest(BaseModel):
    restaurantId: int
    reservationStart: datetime
    reservationEnd: datetime
    partySize: int | None = None


class AvailableTable(BaseModel):
    id: int
    number: str
    capacity: int

    class Config:
        from_attributes = True


class ReservationAvailabilityResponse(BaseModel):
    available: bool
    availableTables: list[AvailableTable]
    message: str | None = None
