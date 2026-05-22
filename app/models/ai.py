from pydantic import BaseModel
from typing import Any


class RecommendRequest(BaseModel):
    cartItemIds: list[int]
    timeOfDay: str


class RecommendResponse(BaseModel):
    recommendations: list[Any]

class SearchRequest(BaseModel):
    query: str
    restaurantId: str | None = None
    limit: int | None = None


class SearchResponse(BaseModel):
    results: list[Any]
