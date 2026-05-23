from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class RecentActivityItem(BaseModel):
    type: str
    id: int
    timestamp: datetime
    restaurantId: Optional[int] = None
    restaurantName: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AdminStatsResponse(BaseModel):
    totalRestaurants: int
    totalOrdersToday: int
    revenueToday: float
    activeUsers: int
    recentActivity: List[RecentActivityItem]


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
    ordersByStatus: Dict[str, int]
    restaurantBreakdown: List[RestaurantAnalyticsItem]


class PlatformSettingsResponse(BaseModel):
    id: int
    currency: str
    timezone: str
    defaultOperatingHours: Dict[str, Any]
    featureFlags: Dict[str, Any]
    updatedAt: datetime

    class Config:
        from_attributes = True


class PlatformSettingsUpdate(BaseModel):
    currency: Optional[str] = None
    timezone: Optional[str] = None
    defaultOperatingHours: Optional[Dict[str, Any]] = None
    featureFlags: Optional[Dict[str, Any]] = None
