from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class RecentActivityItem(BaseModel):
    type: str
    id: int
    timestamp: datetime
    restaurantId: int | None = None
    restaurantName: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AdminStatsResponse(BaseModel):
    totalRestaurants: int
    totalOrdersToday: int
    revenueToday: float
    activeUsers: int
    recentActivity: list[RecentActivityItem]


class RestaurantAnalyticsItem(BaseModel):
    restaurantId: int
    restaurantName: str
    orderCount: int
    revenue: float


class AdminAnalyticsResponse(BaseModel):
    range: AnalyticsRange
    windowStart: datetime
    windowEnd: datetime
    totalRestaurants: int
    activeRestaurants: int
    totalOrders: int
    totalRevenue: float
    averageOrderValue: float
    uniqueCustomers: int
    totalReservations: int
    totalReviews: int
    ordersByStatus: dict[str, int]
    restaurantBreakdown: list[RestaurantAnalyticsItem]


class PlatformSettingsResponse(BaseModel):
    id: int
    currency: str
    timezone: str
    defaultOperatingHours: dict[str, Any]
    featureFlags: dict[str, Any]
    updatedAt: datetime

    class Config:
        from_attributes = True


class PlatformSettingsUpdate(BaseModel):
    currency: str | None = None
    timezone: str | None = None
    defaultOperatingHours: dict[str, Any] | None = None
    featureFlags: dict[str, Any] | None = None
