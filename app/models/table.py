from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TableStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"


class TableBase(BaseModel):
    number: str = Field(..., min_length=1, max_length=10)
    capacity: int = Field(..., ge=1, le=20)
    isActive: bool = True
    status: TableStatus = TableStatus.AVAILABLE
    qrCode: str | None = None
    nfcTag: str | None = None


class TableCreate(TableBase):
    restaurantId: int


class TableUpdate(BaseModel):
    number: str | None = Field(None, min_length=1, max_length=10)
    capacity: int | None = Field(None, ge=1, le=20)
    isActive: bool | None = None
    status: TableStatus | None = None
    qrCode: str | None = None
    nfcTag: str | None = None


class TableResponse(BaseModel):
    id: int
    restaurantId: int
    number: str
    capacity: int
    isActive: bool
    status: TableStatus
    qrCode: str | None
    nfcTag: str | None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class TableListResponse(BaseModel):
    id: int
    number: str
    capacity: int
    isActive: bool
    status: TableStatus
    qrCode: str | None
    currentSession: CurrentOccupantInfo | None = None
    activeOrdersCount: int = 0

    class Config:
        from_attributes = True


class CurrentOccupantInfo(BaseModel):
    sessionId: int
    waiterId: int
    waiterName: str
    startedAt: datetime


class TableCheckinResponse(BaseModel):
    tableId: int
    status: TableStatus
    sessionId: int | None = None
