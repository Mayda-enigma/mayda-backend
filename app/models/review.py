from datetime import datetime

from pydantic import BaseModel, Field, validator


class ReviewCreate(BaseModel):
    restaurantId: int
    dishId: int | None = None  # Optional - can review restaurant or specific dish
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: str | None = None

    @validator("rating")
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None

    @validator("rating")
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewResponse(BaseModel):
    id: int
    userId: int
    user: dict | None = None  # User's first name, last name
    restaurantId: int
    restaurant: dict | None = None  # Restaurant name
    dishId: int | None = None
    dish: dict | None = None  # Dish name if reviewing specific dish
    rating: int
    comment: str | None
    sentiment: str | None = None  # AI-generated sentiment analysis
    sentimentScore: float | None = None
    isVerified: bool = False  # If user actually ordered from restaurant
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    id: int
    userId: int
    customerName: str | None = None
    restaurantId: int
    restaurantName: str | None = None
    dishId: int | None = None
    dishName: str | None = None
    rating: int
    comment: str | None
    sentiment: str | None = None
    isVerified: bool = False
    createdAt: datetime

    class Config:
        from_attributes = True


class ReviewStats(BaseModel):
    totalReviews: int
    averageRating: float
    ratingDistribution: dict  # {1: count, 2: count, 3: count, 4: count, 5: count}
    verifiedReviews: int
    latestReviews: list[ReviewListResponse]


class RestaurantReviewsResponse(BaseModel):
    restaurant: dict
    stats: ReviewStats
    reviews: list[ReviewListResponse]


class DishReviewsResponse(BaseModel):
    dish: dict
    restaurant: dict
    stats: ReviewStats
    reviews: list[ReviewListResponse]
