from pydantic import BaseModel


class RevenuePoint(BaseModel):
    date: str
    amount: float


class ChannelData(BaseModel):
    channel: str
    count: int


class PeakHour(BaseModel):
    hour: int
    order_count: int


class InfraService(BaseModel):
    service: str
    status: str
    latency_ms: float
    uptime_pct: float


class ActivityItem(BaseModel):
    label: str
    meta: str
    created_at: str


class TopRestaurant(BaseModel):
    name: str
    city: str
    revenue: float
