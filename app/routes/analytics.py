from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db_session
from app.middleware.roles import get_current_staff_user, get_current_user
from app.models.analytics import (
    AnalyticsRange,
    HourlyMetricItem,
    KitchenAnalyticsResponse,
    RestaurantAnalyticsResponse,
    TopDishItem,
)
from app.models.user import UserRole


router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_window_start(range_value: AnalyticsRange, window_end: datetime) -> datetime:
    if range_value == AnalyticsRange.WEEK:
        return window_end - timedelta(days=7)
    if range_value == AnalyticsRange.MONTH:
        return window_end - timedelta(days=30)
    return window_end - timedelta(days=1)


def build_hourly_metrics(orders) -> list[HourlyMetricItem]:
    hourly_counts = {hour: 0 for hour in range(24)}
    for order in orders:
        hourly_counts[order.orderTime.hour] += 1

    return [
        HourlyMetricItem(hour=hour, orderCount=hourly_counts[hour])
        for hour in range(24)
    ]


def get_order_prep_end_time(order):
    return order.preparedAt or order.readyAt or order.completedAt


def get_user_restaurant_id(current_user) -> int:
    if not current_user.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A restaurant association is required for analytics access",
        )
    return current_user.restaurantId


async def get_restaurant_orders_for_range(db: "Prisma", restaurant_id: int, time_range: AnalyticsRange):
    window_end = datetime.now()
    window_start = get_window_start(time_range, window_end)

    orders = await db.order.find_many(
        where={
            "restaurantId": restaurant_id,
            "orderTime": {
                "gte": window_start,
                "lte": window_end,
            },
        },
        include={
            "items": {
                "include": {
                    "dish": True
                }
            }
        },
    )

    return orders


@router.get("/restaurant", response_model=RestaurantAnalyticsResponse)
async def get_restaurant_analytics(
    time_range: AnalyticsRange = Query(AnalyticsRange.DAY, alias="range"),
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get manager dashboard analytics for the current user's restaurant."""

    if current_user.role != UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )

    restaurant_id = get_user_restaurant_id(current_user)
    orders = await get_restaurant_orders_for_range(db, restaurant_id, time_range)

    completed_or_active_orders = [order for order in orders if order.status != "CANCELLED"]
    revenue = round(sum(order.totalAmount for order in completed_or_active_orders), 2)
    order_count = len(completed_or_active_orders)
    avg_order_value = round(revenue / order_count, 2) if order_count else 0.0

    top_dishes = {}
    for order in completed_or_active_orders:
        for item in order.items:
            dish_name = item.dish.name if item.dish else f"Dish {item.dishId}"
            if item.dishId not in top_dishes:
                top_dishes[item.dishId] = {
                    "dishId": item.dishId,
                    "dishName": dish_name,
                    "quantitySold": 0,
                    "revenue": 0.0,
                }

            top_dishes[item.dishId]["quantitySold"] += item.quantity
            top_dishes[item.dishId]["revenue"] += item.totalPrice

    top_dish_items = [
        TopDishItem(
            dishId=data["dishId"],
            dishName=data["dishName"],
            quantitySold=data["quantitySold"],
            revenue=round(data["revenue"], 2),
        )
        for data in top_dishes.values()
    ]
    top_dish_items.sort(key=lambda item: (item.quantitySold, item.revenue), reverse=True)

    return RestaurantAnalyticsResponse(
        revenue=revenue,
        orderCount=order_count,
        avgOrderValue=avg_order_value,
        topDishes=top_dish_items[:5],
        hourlyHeatmap=build_hourly_metrics(completed_or_active_orders),
    )


@router.get("/kitchen", response_model=KitchenAnalyticsResponse)
async def get_kitchen_analytics(
    time_range: AnalyticsRange = Query(AnalyticsRange.DAY, alias="range"),
    current_user=Depends(get_current_staff_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get kitchen dashboard analytics for the current staff user's restaurant."""

    restaurant_id = get_user_restaurant_id(current_user)
    orders = await get_restaurant_orders_for_range(db, restaurant_id, time_range)

    prep_durations = []
    late_orders = 0
    late_eligible_orders = 0

    for order in orders:
        prep_end = get_order_prep_end_time(order)
        if order.confirmedAt and prep_end:
            prep_minutes = (prep_end - order.confirmedAt).total_seconds() / 60
            if prep_minutes >= 0:
                prep_durations.append(prep_minutes)

        if order.estimatedDeliveryTime and prep_end:
            late_eligible_orders += 1
            if prep_end > order.estimatedDeliveryTime:
                late_orders += 1

    avg_prep_minutes = round(sum(prep_durations) / len(prep_durations), 2) if prep_durations else 0.0
    late_order_rate = round((late_orders / late_eligible_orders) * 100, 2) if late_eligible_orders else 0.0

    return KitchenAnalyticsResponse(
        avgPrepMinutes=avg_prep_minutes,
        ordersPerHour=build_hourly_metrics([order for order in orders if order.status != "CANCELLED"]),
        lateOrderRate=late_order_rate,
    )
