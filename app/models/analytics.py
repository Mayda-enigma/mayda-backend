from enum import Enum
from pydantic import BaseModel


class AnalyticsRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class TopDishItem(BaseModel):
    dishId: int
    dishName: str
    quantitySold: int
    revenue: float


class HourlyMetricItem(BaseModel):
    hour: int
    orderCount: int


class RestaurantAnalyticsResponse(BaseModel):
    revenue: float
    orderCount: int
    avgOrderValue: float
    topDishes: list[TopDishItem]
    hourlyHeatmap: list[HourlyMetricItem]


class KitchenAnalyticsResponse(BaseModel):
    avgPrepMinutes: float
    ordersPerHour: list[HourlyMetricItem]
    lateOrderRate: float
    orderCount: int
    revenue: float
    topDishes: list[TopDishItem]
