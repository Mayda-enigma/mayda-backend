from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ReservationStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class ReservationCreate(BaseModel):
    restaurantId: int
    tableId: Optional[int] = None
    reservationStart: datetime
    reservationEnd: datetime
    # Note: No customer info needed - uses authenticated user's profile automatically
    specialRequests: Optional[str] = None  # Any special requests for the reservation
    partySize: Optional[int] = None  # Number of people (helps with table selection)
    
    @validator('reservationEnd')
    def validate_end_time(cls, v, values):
        if 'reservationStart' in values and v <= values['reservationStart']:
            raise ValueError('Reservation end time must be after start time')
        return v
    
    @validator('reservationStart')
    def validate_start_time(cls, v):
        if v <= datetime.now():
            raise ValueError('Reservation start time must be in the future')
        return v


class PublicReservationCreate(BaseModel):
    """For staff creating reservations on behalf of customers (phone bookings, walk-ins)."""
    restaurantId: int
    tableId: Optional[int] = None
    reservationStart: datetime
    reservationEnd: datetime
    customerName: str
    customerPhone: str
    customerEmail: Optional[str] = None
    partySize: Optional[int] = None
    specialRequests: Optional[str] = None
    
    @validator('reservationEnd')
    def validate_end_time(cls, v, values):
        if 'reservationStart' in values and v <= values['reservationStart']:
            raise ValueError('Reservation end time must be after start time')
        return v
    
    @validator('reservationStart')
    def validate_start_time(cls, v):
        if v <= datetime.now():
            raise ValueError('Reservation start time must be in the future')
        return v


class ReservationUpdate(BaseModel):
    tableId: Optional[int] = None
    reservationStart: Optional[datetime] = None
    reservationEnd: Optional[datetime] = None
    
    @validator('reservationEnd')
    def validate_end_time(cls, v, values):
        if v and 'reservationStart' in values and values['reservationStart'] and v <= values['reservationStart']:
            raise ValueError('Reservation end time must be after start time')
        return v


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationResponse(BaseModel):
    id: int
    userId: Optional[int]
    user: Optional[dict] = None
    tableId: Optional[int]
    table: Optional[dict] = None
    restaurantId: int
    restaurant: Optional[dict] = None
    reservationStart: datetime
    reservationEnd: datetime
    status: ReservationStatus
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class ReservationListResponse(BaseModel):
    id: int
    userId: Optional[int]
    customerName: Optional[str] = None
    customerPhone: Optional[str] = None
    tableId: Optional[int]
    tableNumber: Optional[str] = None
    restaurantId: int
    restaurantName: Optional[str] = None
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
    partySize: Optional[int] = None


class AvailableTable(BaseModel):
    id: int
    number: str
    capacity: int
    
    class Config:
        from_attributes = True


class ReservationAvailabilityResponse(BaseModel):
    available: bool
    availableTables: List[AvailableTable]
    message: Optional[str] = None
