from pydantic import BaseModel


class Anomaly(BaseModel):
    id: int
    severity: str
    title: str
    detail: str
    detected_at: str
    acknowledged: bool


class AnomalyAckResponse(BaseModel):
    success: bool


class AnomalyStats(BaseModel):
    total: int
    critical_unacknowledged: int
    unacknowledged: int
    by_severity: list[dict]
