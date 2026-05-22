from enum import Enum
from pydantic import BaseModel


class AnalyticsRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class TopDish(BaseModel):
    dishId: int
    dishName: str
    quantity: int


class HourlyBucket(BaseModel):
    hour: int
    count: int


class RestaurantAnalyticsResponse(BaseModel):
    revenue: float
    orderCount: int
    avgOrderValue: float
    topDishes: list[TopDish]
    hourlyHeatmap: list[HourlyBucket]


class KitchenAnalyticsResponse(BaseModel):
    avgPrepMinutes: float
    ordersPerHour: list[HourlyBucket]
    lateOrderRate: float
