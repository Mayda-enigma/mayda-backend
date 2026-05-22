from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class PromotionType(str, Enum):
    DISCOUNT = "DISCOUNT"
    BOGO = "BOGO"  # Buy One Get One
    FREE_DELIVERY = "FREE_DELIVERY"
    HAPPY_HOUR = "HAPPY_HOUR"
    SEASONAL = "SEASONAL"


class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class PromotionCreate(BaseModel):
    restaurantId: int
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    image: Optional[str] = None
    type: PromotionType
    discountType: DiscountType
    discountValue: float = Field(..., gt=0)
    minOrderAmount: Optional[float] = Field(None, ge=0)
    startDate: datetime
    endDate: datetime
    maxUses: Optional[int] = Field(None, gt=0)
    dishIds: Optional[List[int]] = []  # Specific dishes this promotion applies to
    
    @validator('endDate')
    def validate_end_date(cls, v, values):
        if 'startDate' in values and v <= values['startDate']:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('startDate')
    def validate_start_date(cls, v):
        if v < datetime.now():
            raise ValueError('Start date cannot be in the past')
        return v
    
    @validator('discountValue')
    def validate_discount_value(cls, v, values):
        if 'discountType' in values:
            if values['discountType'] == DiscountType.PERCENTAGE:
                if v > 100:
                    raise ValueError('Percentage discount cannot exceed 100%')
        return v


class PromotionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    image: Optional[str] = None
    discountValue: Optional[float] = Field(None, gt=0)
    minOrderAmount: Optional[float] = Field(None, ge=0)
    endDate: Optional[datetime] = None
    maxUses: Optional[int] = Field(None, gt=0)
    isActive: Optional[bool] = None
    dishIds: Optional[List[int]] = None


class PromotionResponse(BaseModel):
    id: int
    restaurantId: int
    restaurant: Optional[dict] = None
    title: str
    description: str
    image: Optional[str]
    type: PromotionType
    discountType: DiscountType
    discountValue: float
    minOrderAmount: Optional[float]
    startDate: datetime
    endDate: datetime
    maxUses: Optional[int]
    currentUses: int
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    dishes: Optional[List[dict]] = []  # Applicable dishes
    
    class Config:
        from_attributes = True


class PromotionListResponse(BaseModel):
    id: int
    restaurantId: int
    restaurantName: Optional[str] = None
    title: str
    description: str
    image: Optional[str]
    type: PromotionType
    discountType: DiscountType
    discountValue: float
    minOrderAmount: Optional[float]
    startDate: datetime
    endDate: datetime
    maxUses: Optional[int]
    currentUses: int
    isActive: bool
    isExpired: bool = False
    dishCount: int = 0  # Number of applicable dishes
    
    class Config:
        from_attributes = True


class PromotionUsageRequest(BaseModel):
    promotionId: int
    orderAmount: float


class PromotionUsageResponse(BaseModel):
    applicable: bool
    discountAmount: float
    finalAmount: float
    message: Optional[str] = None


class ActivePromotionsResponse(BaseModel):
    totalPromotions: int
    restaurantPromotions: List[PromotionListResponse]
    dishSpecificPromotions: List[PromotionListResponse]
