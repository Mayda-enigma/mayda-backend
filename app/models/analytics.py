from enum import Enum

from pydantic import BaseModel


class AnalyticsRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"


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


class KpisResponse(BaseModel):
    totalRevenue: float
    totalOrders: int
    avgOrderValue: float
    customerRating: float
    revenueTrend: float
    ordersTrend: float
    avgOrderValueTrend: float
    ratingTrend: float


class DailyRevenueItem(BaseModel):
    name: str
    revenue: float
    orders: int
    profit: float


class ForecastItem(BaseModel):
    revenue: float
    change: float


class RevenueResponse(BaseModel):
    salesData: list[DailyRevenueItem]
    forecast: ForecastItem


class TopDishFrontendItem(BaseModel):
    name: str
    orders: int
    revenue: float
    rating: float
    trend: str


class HourlyDataPoint(BaseModel):
    hour: str
    orders: int
    revenue: float


class CuisineShareItem(BaseModel):
    name: str
    value: int
    color: str
    orders: int


class AlertItem(BaseModel):
    type: str
    title: str
    message: str
    color: str


class PerformanceMetricsResponse(BaseModel):
    avgPrepTime: int
    orderAccuracy: float
    tableTurnoverRate: str
    staffEfficiency: int
    alerts: list[AlertItem]


class MonthlyComparisonItem(BaseModel):
    month: str
    thisYear: float
    lastYear: float
