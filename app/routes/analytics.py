from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db_session
from app.middleware.roles import get_current_manager_or_admin, get_current_staff_user
from app.models.analytics import (
    AnalyticsRange,
    HourlyBucket,
    KitchenAnalyticsResponse,
    RestaurantAnalyticsResponse,
    TopDish,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _range_start(range_value: AnalyticsRange) -> datetime:
    now = datetime.now()
    if range_value == AnalyticsRange.DAY:
        return now - timedelta(days=1)
    if range_value == AnalyticsRange.WEEK:
        return now - timedelta(days=7)
    return now - timedelta(days=30)


def _base_where(start: datetime, restaurant_id: int | None) -> dict[str, Any]:
    where: dict[str, Any] = {"orderTime": {"gte": start}}
    if restaurant_id:
        where["restaurantId"] = restaurant_id
    return where


def _metric_value(container: Any, key: str) -> float:
    if not container:
        return 0.0
    if isinstance(container, dict):
        return float(container.get(key) or 0)
    return float(getattr(container, key, 0) or 0)


@router.get("/restaurant", response_model=RestaurantAnalyticsResponse)
async def get_restaurant_analytics(
    range: AnalyticsRange = Query(AnalyticsRange.DAY),
    current_user=Depends(get_current_manager_or_admin),
    db=Depends(get_db_session),
) -> RestaurantAnalyticsResponse:
    start = _range_start(range)
    where = _base_where(start, getattr(current_user, "restaurantId", None))

    aggregate = await db.order.aggregate(
        where=where,
        _sum={"totalAmount": True},
        _count={"id": True},
    )
    revenue = _metric_value(getattr(aggregate, "_sum", None), "totalAmount")
    order_count = int(_metric_value(getattr(aggregate, "_count", None), "id"))
    avg_order_value = revenue / order_count if order_count else 0.0

    restaurant_filter = 'AND o."restaurantId" = $2' if getattr(current_user, "restaurantId", None) else ""
    top_dishes_query = f"""
        SELECT
            oi."dishId" AS "dishId",
            d.name AS "dishName",
            SUM(oi.quantity)::int AS quantity
        FROM "order_items" oi
        JOIN "orders" o ON o.id = oi."orderId"
        JOIN "dishes" d ON d.id = oi."dishId"
        WHERE o."orderTime" >= $1
        {restaurant_filter}
        GROUP BY oi."dishId", d.name
        ORDER BY quantity DESC
        LIMIT 5
    """
    hourly_heatmap_query = f"""
        SELECT
            EXTRACT(HOUR FROM o."orderTime")::int AS hour,
            COUNT(*)::int AS count
        FROM "orders" o
        WHERE o."orderTime" >= $1
        {restaurant_filter}
        GROUP BY hour
        ORDER BY hour
    """

    query_args = (start, current_user.restaurantId) if getattr(current_user, "restaurantId", None) else (start,)
    top_dishes_result = await db.query_raw(top_dishes_query, *query_args)
    hourly_heatmap_result = await db.query_raw(hourly_heatmap_query, *query_args)

    top_dishes = [
        TopDish(dishId=row["dishId"], dishName=row["dishName"], quantity=row["quantity"])
        for row in top_dishes_result
    ]
    hourly_heatmap = [
        HourlyBucket(hour=row["hour"], count=row["count"])
        for row in hourly_heatmap_result
    ]

    return RestaurantAnalyticsResponse(
        revenue=revenue,
        orderCount=order_count,
        avgOrderValue=avg_order_value,
        topDishes=top_dishes,
        hourlyHeatmap=hourly_heatmap,
    )


@router.get("/kitchen", response_model=KitchenAnalyticsResponse)
async def get_kitchen_analytics(
    range: AnalyticsRange = Query(AnalyticsRange.DAY),
    current_user=Depends(get_current_staff_user),
    db=Depends(get_db_session),
) -> KitchenAnalyticsResponse:
    start = _range_start(range)
    restaurant_filter = 'AND o."restaurantId" = $2' if getattr(current_user, "restaurantId", None) else ""

    prep_query = f"""
        SELECT COALESCE(
            AVG(EXTRACT(EPOCH FROM (o."completedAt" - o."preparedAt")) / 60.0),
            0
        ) AS "avgPrepMinutes"
        FROM "orders" o
        WHERE o."orderTime" >= $1
          AND o."preparedAt" IS NOT NULL
          AND o."completedAt" IS NOT NULL
          {restaurant_filter}
    """
    orders_per_hour_query = f"""
        SELECT
            EXTRACT(HOUR FROM o."orderTime")::int AS hour,
            COUNT(*)::int AS count
        FROM "orders" o
        WHERE o."orderTime" >= $1
          {restaurant_filter}
        GROUP BY hour
        ORDER BY hour
    """
    late_rate_query = f"""
        SELECT COALESCE(
            (
                SUM(CASE WHEN o."actualDeliveryTime" > o."estimatedDeliveryTime" THEN 1 ELSE 0 END)::float
                / NULLIF(COUNT(*), 0)
            ) * 100,
            0
        ) AS "lateOrderRate"
        FROM "orders" o
        WHERE o."orderTime" >= $1
          AND o."estimatedDeliveryTime" IS NOT NULL
          AND o."actualDeliveryTime" IS NOT NULL
          {restaurant_filter}
    """

    query_args = (start, current_user.restaurantId) if getattr(current_user, "restaurantId", None) else (start,)
    prep_result = await db.query_raw(prep_query, *query_args)
    orders_per_hour_result = await db.query_raw(orders_per_hour_query, *query_args)
    late_rate_result = await db.query_raw(late_rate_query, *query_args)

    avg_prep_minutes = float(prep_result[0]["avgPrepMinutes"]) if prep_result else 0.0
    late_order_rate = float(late_rate_result[0]["lateOrderRate"]) if late_rate_result else 0.0
    orders_per_hour = [
        HourlyBucket(hour=row["hour"], count=row["count"])
        for row in orders_per_hour_result
    ]

    return KitchenAnalyticsResponse(
        avgPrepMinutes=avg_prep_minutes,
        ordersPerHour=orders_per_hour,
        lateOrderRate=late_order_rate,
    )
