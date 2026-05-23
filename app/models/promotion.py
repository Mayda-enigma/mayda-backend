from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator


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
    image: str | None = None
    type: PromotionType
    discountType: DiscountType
    discountValue: float = Field(..., gt=0)
    minOrderAmount: float | None = Field(None, ge=0)
    startDate: datetime
    endDate: datetime
    maxUses: int | None = Field(None, gt=0)
    dishIds: list[int] | None = []  # Specific dishes this promotion applies to

    @validator("endDate")
    def validate_end_date(cls, v, values):
        if "startDate" in values and v <= values["startDate"]:
            raise ValueError("End date must be after start date")
        return v

    @validator("startDate")
    def validate_start_date(cls, v):
        if v < datetime.now():
            raise ValueError("Start date cannot be in the past")
        return v

    @validator("discountValue")
    def validate_discount_value(cls, v, values):
        if "discountType" in values:  # noqa: SIM102
            if values["discountType"] == DiscountType.PERCENTAGE:  # noqa: SIM102
                if v > 100:
                    raise ValueError("Percentage discount cannot exceed 100%")
        return v


class PromotionUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=500)
    image: str | None = None
    discountValue: float | None = Field(None, gt=0)
    minOrderAmount: float | None = Field(None, ge=0)
    endDate: datetime | None = None
    maxUses: int | None = Field(None, gt=0)
    isActive: bool | None = None
    dishIds: list[int] | None = None


class PromotionResponse(BaseModel):
    id: int
    restaurantId: int
    restaurant: dict | None = None
    title: str
    description: str
    image: str | None
    type: PromotionType
    discountType: DiscountType
    discountValue: float
    minOrderAmount: float | None
    startDate: datetime
    endDate: datetime
    maxUses: int | None
    currentUses: int
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    dishes: list[dict] | None = []  # Applicable dishes

    class Config:
        from_attributes = True


class PromotionListResponse(BaseModel):
    id: int
    restaurantId: int
    restaurantName: str | None = None
    title: str
    description: str
    image: str | None
    type: PromotionType
    discountType: DiscountType
    discountValue: float
    minOrderAmount: float | None
    startDate: datetime
    endDate: datetime
    maxUses: int | None
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
    message: str | None = None


class ActivePromotionsResponse(BaseModel):
    totalPromotions: int
    restaurantPromotions: list[PromotionListResponse]
    dishSpecificPromotions: list[PromotionListResponse]
