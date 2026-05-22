from pydantic import BaseModel
from typing import Any


class RecommendRequest(BaseModel):
    cartItemIds: list[int]
    timeOfDay: str


class RecommendResponse(BaseModel):
    recommendations: list[Any]
