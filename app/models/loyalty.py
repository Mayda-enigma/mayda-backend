from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime


class LoyaltyCardCreate(BaseModel):
    # Loyalty cards are automatically created when users make their first order
    # No manual creation needed - this is for internal use
    pass


class LoyaltyCardResponse(BaseModel):
    id: int
    userId: int
    user: Optional[dict] = None  # User details
    points: int
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class LoyaltyTransactionCreate(BaseModel):
    loyaltyCardId: int
    restaurantId: int
    points: int  # Can be positive (earned) or negative (redeemed)
    type: str = Field(..., min_length=1)  # "EARNED", "REDEEMED", "BONUS", "EXPIRED"
    description: str = Field(..., min_length=1, max_length=255)
    orderId: Optional[int] = None  # Link to order if points earned from purchase
    
    @validator('points')
    def validate_points(cls, v, values):
        if 'type' in values:
            if values['type'] == "REDEEMED" and v > 0:
                raise ValueError('Redeemed points must be negative')
            elif values['type'] in ["EARNED", "BONUS"] and v <= 0:
                raise ValueError('Earned/bonus points must be positive')
        return v


class LoyaltyTransactionResponse(BaseModel):
    id: int
    loyaltyCardId: int
    loyaltyCard: Optional[dict] = None
    restaurantId: int
    restaurant: Optional[dict] = None
    points: int
    type: str
    description: str
    orderId: Optional[int] = None
    order: Optional[dict] = None
    createdAt: datetime
    
    class Config:
        from_attributes = True


class LoyaltyTransactionListResponse(BaseModel):
    id: int
    restaurantId: int
    restaurantName: Optional[str] = None
    points: int
    type: str
    description: str
    orderId: Optional[int] = None
    orderNumber: Optional[str] = None
    createdAt: datetime
    
    class Config:
        from_attributes = True


class PointsRedemptionRequest(BaseModel):
    restaurantId: int
    pointsToRedeem: int = Field(..., gt=0)
    description: Optional[str] = "Points redeemed for discount"
    
    @validator('pointsToRedeem')
    def validate_points(cls, v):
        if v <= 0:
            raise ValueError('Points to redeem must be greater than 0')
        if v % 10 != 0:  # Points usually redeemed in multiples of 10
            raise ValueError('Points must be redeemed in multiples of 10')
        return v


class PointsRedemptionResponse(BaseModel):
    success: bool
    pointsRedeemed: int
    discountAmount: float  # Monetary value of redeemed points
    remainingPoints: int
    message: str


class PointsEarnedRequest(BaseModel):
    orderId: int
    restaurantId: int
    orderAmount: float
    
    @validator('orderAmount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Order amount must be greater than 0')
        return v


class PointsEarnedResponse(BaseModel):
    pointsEarned: int
    totalPoints: int
    message: str


class LoyaltyStatsResponse(BaseModel):
    totalPoints: int
    pointsEarned: int
    pointsRedeemed: int
    transactionCount: int
    favoriteRestaurants: List[dict]  # Top restaurants by points earned
    recentTransactions: List[LoyaltyTransactionListResponse]


class RestaurantLoyaltyStatsResponse(BaseModel):
    restaurantId: int
    restaurantName: str
    totalCustomers: int
    totalPointsGiven: int
    totalPointsRedeemed: int
    averagePointsPerCustomer: float
    topCustomers: List[dict]  # Customers with most points
    recentTransactions: List[LoyaltyTransactionListResponse]


class LoyaltyProgramInfo(BaseModel):
    pointsPerDollar: float  # How many points earned per dollar spent
    pointsToMoneyRatio: int  # How many points equal 1 dollar
    minimumRedemption: int  # Minimum points required to redeem
