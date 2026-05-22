from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime


class ReviewCreate(BaseModel):
    restaurantId: int
    dishId: Optional[int] = None  # Optional - can review restaurant or specific dish
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Rating must be between 1 and 5')
        return v


class ReviewResponse(BaseModel):
    id: int
    userId: int
    user: Optional[dict] = None  # User's first name, last name
    restaurantId: int
    restaurant: Optional[dict] = None  # Restaurant name
    dishId: Optional[int] = None
    dish: Optional[dict] = None  # Dish name if reviewing specific dish
    rating: int
    comment: Optional[str]
    sentiment: Optional[str] = None  # AI-generated sentiment analysis
    sentimentScore: Optional[float] = None
    isVerified: bool = False  # If user actually ordered from restaurant
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    id: int
    userId: int
    customerName: Optional[str] = None
    restaurantId: int
    restaurantName: Optional[str] = None
    dishId: Optional[int] = None
    dishName: Optional[str] = None
    rating: int
    comment: Optional[str]
    sentiment: Optional[str] = None
    isVerified: bool = False
    createdAt: datetime
    
    class Config:
        from_attributes = True


class ReviewStats(BaseModel):
    totalReviews: int
    averageRating: float
    ratingDistribution: dict  # {1: count, 2: count, 3: count, 4: count, 5: count}
    verifiedReviews: int
    latestReviews: List[ReviewListResponse]


class RestaurantReviewsResponse(BaseModel):
    restaurant: dict
    stats: ReviewStats
    reviews: List[ReviewListResponse]


class DishReviewsResponse(BaseModel):
    dish: dict
    restaurant: dict
    stats: ReviewStats
    reviews: List[ReviewListResponse]
