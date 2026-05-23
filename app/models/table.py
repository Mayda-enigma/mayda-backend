from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TableStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"


class TableBase(BaseModel):
    number: str = Field(..., min_length=1, max_length=10)
    capacity: int = Field(..., ge=1, le=20)
    isActive: bool = True
    status: TableStatus = TableStatus.AVAILABLE
    qrCode: Optional[str] = None
    nfcTag: Optional[str] = None


class TableCreate(TableBase):
    restaurantId: int


class TableUpdate(BaseModel):
    number: Optional[str] = Field(None, min_length=1, max_length=10)
    capacity: Optional[int] = Field(None, ge=1, le=20)
    isActive: Optional[bool] = None
    status: Optional[TableStatus] = None
    qrCode: Optional[str] = None
    nfcTag: Optional[str] = None


class TableResponse(BaseModel):
    id: int
    restaurantId: int
    number: str
    capacity: int
    isActive: bool
    status: TableStatus
    qrCode: Optional[str]
    nfcTag: Optional[str]
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
    qrCode: Optional[str]
    
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
    sessionId: Optional[int] = None
