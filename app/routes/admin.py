from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db_session
from app.middleware.roles import get_current_admin_user
from app.models.admin import (
    AdminAnalyticsResponse,
    AdminStatsResponse,
    AnalyticsRange,
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
    RecentActivityItem,
    RestaurantAnalyticsItem,
)


router = APIRouter(prefix="/admin", tags=["Admin"])

DEFAULT_OPERATING_HOURS = {
    "monday": "08:00-23:00",
    "tuesday": "08:00-23:00",
    "wednesday": "08:00-23:00",
    "thursday": "08:00-23:00",
    "friday": "08:00-23:00",
    "saturday": "08:00-23:00",
    "sunday": "08:00-23:00",
}


def build_default_platform_settings() -> Dict[str, Any]:
    return {
        "id": 1,
        "currency": "USD",
        "timezone": "UTC",
        "defaultOperatingHours": DEFAULT_OPERATING_HOURS.copy(),
        "featureFlags": {},
    }


def get_window_start(range_value: AnalyticsRange, window_end: datetime) -> datetime:
    if range_value == AnalyticsRange.WEEK:
        return window_end - timedelta(days=7)
    if range_value == AnalyticsRange.MONTH:
        return window_end - timedelta(days=30)
    return window_end - timedelta(days=1)


async def get_or_create_platform_settings(db: "Prisma"):
    existing_rows = await db.platformsettings.find_many(
        take=1,
        order={"id": "asc"},
    )
    if existing_rows:
        return existing_rows[0]

    try:
        return await db.platformsettings.create(data=build_default_platform_settings())
    except Exception as exc:
        existing_rows = await db.platformsettings.find_many(
            take=1,
            order={"id": "asc"},
        )
        if existing_rows:
            return existing_rows[0]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating platform settings: {str(exc)}",
        )


def build_recent_activity_items(orders, reservations, reviews):
    recent_activity = []

    for order in orders:
        recent_activity.append(
            RecentActivityItem(
                type="order",
                id=order.id,
                timestamp=order.orderTime,
                restaurantId=order.restaurantId,
                restaurantName=order.restaurant.name if order.restaurant else None,
                details={
                    "orderNumber": order.orderNumber,
                    "status": order.status,
                    "totalAmount": round(order.totalAmount, 2),
                },
            )
        )

    for reservation in reservations:
        recent_activity.append(
            RecentActivityItem(
                type="reservation",
                id=reservation.id,
                timestamp=reservation.createdAt,
                restaurantId=reservation.restaurantId,
                restaurantName=reservation.restaurant.name if reservation.restaurant else None,
                details={
                    "status": reservation.status,
                    "reservationStart": reservation.reservationStart.isoformat(),
                },
            )
        )

    for review in reviews:
        recent_activity.append(
            RecentActivityItem(
                type="review",
                id=review.id,
                timestamp=review.createdAt,
                restaurantId=review.restaurantId,
                restaurantName=review.restaurant.name if review.restaurant else None,
                details={
                    "rating": review.rating,
                    "comment": review.comment,
                },
            )
        )

    recent_activity.sort(key=lambda item: item.timestamp, reverse=True)
    return recent_activity[:10]


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get platform-wide dashboard stats (Admin only)."""

    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    total_restaurants = await db.restaurant.count()
    total_orders_today = await db.order.count(
        where={"orderTime": {"gte": start_of_today}}
    )
    active_users = await db.user.count(where={"isActive": True})

    todays_orders = await db.order.find_many(
        where={"orderTime": {"gte": start_of_today}}
    )
    revenue_today = round(
        sum(order.totalAmount for order in todays_orders if order.status != "CANCELLED"),
        2,
    )

    recent_orders = await db.order.find_many(
        include={"restaurant": {"select": {"name": True}}},
        order={"orderTime": "desc"},
        take=5,
    )
    recent_reservations = await db.reservation.find_many(
        include={"restaurant": {"select": {"name": True}}},
        order={"createdAt": "desc"},
        take=3,
    )
    recent_reviews = await db.review.find_many(
        include={"restaurant": {"select": {"name": True}}},
        order={"createdAt": "desc"},
        take=3,
    )

    return AdminStatsResponse(
        totalRestaurants=total_restaurants,
        totalOrdersToday=total_orders_today,
        revenueToday=revenue_today,
        activeUsers=active_users,
        recentActivity=build_recent_activity_items(
            recent_orders,
            recent_reservations,
            recent_reviews,
        ),
    )


@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def get_admin_analytics(
    time_range: AnalyticsRange = Query(AnalyticsRange.DAY, alias="range"),
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get platform-wide analytics for a requested time window (Admin only)."""

    window_end = datetime.now()
    window_start = get_window_start(time_range, window_end)

    orders = await db.order.find_many(
        where={
            "orderTime": {
                "gte": window_start,
                "lte": window_end,
            }
        },
        include={"restaurant": {"select": {"name": True}}},
    )
    total_restaurants = await db.restaurant.count()
    total_reservations = await db.reservation.count(
        where={
            "createdAt": {
                "gte": window_start,
                "lte": window_end,
            }
        }
    )
    total_reviews = await db.review.count(
        where={
            "createdAt": {
                "gte": window_start,
                "lte": window_end,
            }
        }
    )

    orders_by_status: Dict[str, int] = {}
    restaurant_breakdown: Dict[int, Dict[str, Any]] = {}
    unique_customers = set()
    revenue_orders = 0
    total_revenue = 0.0

    for order in orders:
        orders_by_status[order.status] = orders_by_status.get(order.status, 0) + 1

        if order.userId:
            unique_customers.add(order.userId)

        restaurant_name = (
            order.restaurant.name
            if order.restaurant
            else f"Restaurant {order.restaurantId}"
        )
        if order.restaurantId not in restaurant_breakdown:
            restaurant_breakdown[order.restaurantId] = {
                "restaurantId": order.restaurantId,
                "restaurantName": restaurant_name,
                "orderCount": 0,
                "revenue": 0.0,
            }

        restaurant_breakdown[order.restaurantId]["orderCount"] += 1

        if order.status != "CANCELLED":
            total_revenue += order.totalAmount
            restaurant_breakdown[order.restaurantId]["revenue"] += order.totalAmount
            revenue_orders += 1

    restaurant_items = [
        RestaurantAnalyticsItem(
            restaurantId=data["restaurantId"],
            restaurantName=data["restaurantName"],
            orderCount=data["orderCount"],
            revenue=round(data["revenue"], 2),
        )
        for data in restaurant_breakdown.values()
    ]
    restaurant_items.sort(key=lambda item: item.revenue, reverse=True)

    return AdminAnalyticsResponse(
        range=time_range,
        windowStart=window_start,
        windowEnd=window_end,
        totalRestaurants=total_restaurants,
        activeRestaurants=len(restaurant_breakdown),
        totalOrders=len(orders),
        totalRevenue=round(total_revenue, 2),
        averageOrderValue=round(total_revenue / revenue_orders, 2) if revenue_orders else 0.0,
        uniqueCustomers=len(unique_customers),
        totalReservations=total_reservations,
        totalReviews=total_reviews,
        ordersByStatus=orders_by_status,
        restaurantBreakdown=restaurant_items,
    )


@router.get("/settings", response_model=PlatformSettingsResponse)
async def get_platform_settings(
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get the single platform settings row (Admin only)."""

    settings_row = await get_or_create_platform_settings(db)
    return PlatformSettingsResponse.model_validate(settings_row)


@router.put("/settings", response_model=PlatformSettingsResponse)
async def update_platform_settings(
    settings_data: PlatformSettingsUpdate,
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Update the single platform settings row (Admin only)."""

    settings_row = await get_or_create_platform_settings(db)

    update_data = {}
    for field, value in settings_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update",
        )

    try:
        updated_settings = await db.platformsettings.update(
            where={"id": settings_row.id},
            data=update_data,
        )
        return PlatformSettingsResponse.model_validate(updated_settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating platform settings: {str(exc)}",
        )
