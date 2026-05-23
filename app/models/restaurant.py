from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    phone: str = Field(..., min_length=10, max_length=20)
    email: EmailStr | None = None
    website: str | None = None
    operatingHours: dict[str, Any] = Field(..., description="Operating hours in JSON format")
    logo: str | None = None
    coverImage: str | None = None
    gallery: list[str] | None = []
    isActive: bool = True


class RestaurantCreate(RestaurantBase):
    # Address fields for creating restaurant with address
    street: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    latitude: float | None = None
    longitude: float | None = None


class RestaurantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    phone: str | None = Field(None, min_length=10, max_length=20)
    email: EmailStr | None = None
    website: str | None = None
    operatingHours: dict[str, Any] | None = None
    logo: str | None = None
    coverImage: str | None = None
    gallery: list[str] | None = None
    isActive: bool | None = None


class AddressResponse(BaseModel):
    id: int
    street: str
    city: str
    latitude: float | None
    longitude: float | None
    isDefault: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class RestaurantResponse(BaseModel):
    id: int
    name: str
    description: str | None
    phone: str
    email: str | None
    website: str | None
    operatingHours: dict[str, Any]
    logo: str | None
    coverImage: str | None
    gallery: list[str]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    address: AddressResponse | None

    class Config:
        from_attributes = True


class RestaurantListResponse(BaseModel):
    id: int
    name: str
    description: str | None
    phone: str
    logo: str | None
    coverImage: str | None
    isActive: bool
    address: AddressResponse | None

    class Config:
        from_attributes = True
