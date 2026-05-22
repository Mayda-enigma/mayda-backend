from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime


class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    operatingHours: Dict[str, Any] = Field(..., description="Operating hours in JSON format")
    logo: Optional[str] = None
    coverImage: Optional[str] = None
    gallery: Optional[List[str]] = []
    isActive: bool = True


class RestaurantCreate(RestaurantBase):
    # Address fields for creating restaurant with address
    street: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    operatingHours: Optional[Dict[str, Any]] = None
    logo: Optional[str] = None
    coverImage: Optional[str] = None
    gallery: Optional[List[str]] = None
    isActive: Optional[bool] = None


class AddressResponse(BaseModel):
    id: int
    street: str
    city: str
    latitude: Optional[float]
    longitude: Optional[float]
    isDefault: bool
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class RestaurantResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    phone: str
    email: Optional[str]
    website: Optional[str]
    operatingHours: Dict[str, Any]
    logo: Optional[str]
    coverImage: Optional[str]
    gallery: List[str]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    address: Optional[AddressResponse]
    
    class Config:
        from_attributes = True


class RestaurantListResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    phone: str
    logo: Optional[str]
    coverImage: Optional[str]
    isActive: bool
    address: Optional[AddressResponse]
    
    class Config:
        from_attributes = True
