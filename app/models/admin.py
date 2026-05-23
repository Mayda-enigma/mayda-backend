from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel


class RecentActivityItem(BaseModel):
    type: str
    id: int
    amount: float
    timestamp: datetime


class AdminStatsResponse(BaseModel):
    totalRestaurants: int
    totalOrdersToday: int
    revenueToday: float
    activeUsers: int
    recentActivity: List[RecentActivityItem]


class AnalyticsRange(str, Enum):
    day = "day"
    week = "week"
    month = "month"


class TopRestaurantMetric(BaseModel):
    restaurantId: int
    restaurantName: str
    orders: int
    revenue: float


class AdminAnalyticsResponse(BaseModel):
    range: AnalyticsRange
    totalOrders: int
    totalRevenue: float
    averageOrderValue: float
    activeRestaurants: int
    topRestaurants: List[TopRestaurantMetric]


class PlatformSettingsResponse(BaseModel):
    id: int
    currency: str
    timezone: str
    defaultOperatingHours: Dict[str, Any]
    featureFlags: Dict[str, Any]
    updatedAt: datetime


class PlatformSettingsUpdate(BaseModel):
    currency: str | None = None
    timezone: str | None = None
    defaultOperatingHours: Dict[str, Any] | None = None
    featureFlags: Dict[str, Any] | None = None
