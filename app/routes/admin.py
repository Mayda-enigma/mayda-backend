from datetime import datetime, timedelta

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
    TopRestaurantMetric,
)


router = APIRouter(prefix="/admin", tags=["Admin"])


def _get_default_operating_hours():
    return {
        "monday": {"open": "09:00", "close": "18:00"},
        "tuesday": {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "thursday": {"open": "09:00", "close": "18:00"},
        "friday": {"open": "09:00", "close": "18:00"},
        "saturday": {"open": "10:00", "close": "16:00"},
        "sunday": {"open": "10:00", "close": "16:00"},
    }


async def _get_or_create_platform_settings(db: "Prisma"):
    platform_settings = await db.platformsettings.find_unique(where={"id": 1})
    if platform_settings:
        return platform_settings

    return await db.platformsettings.create(
        data={
            "id": 1,
            "currency": "USD",
            "timezone": "UTC",
            "defaultOperatingHours": _get_default_operating_hours(),
            "featureFlags": {},
        }
    )


@router.get("/stats", response_model=AdminStatsResponse)
async def get_platform_stats(
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    del current_user
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day)

    try:
        total_restaurants = await db.restaurant.count()
        active_users = await db.user.count(where={"isActive": True})
        today_orders = await db.order.find_many(
            where={"orderTime": {"gte": start_of_day}},
            include={"user": {"select": {"firstName": True, "lastName": True}}},
            order={"orderTime": "desc"},
            take=10,
        )

        revenue_today = sum(float(order.totalAmount) for order in today_orders)
        recent_activity = [
            RecentActivityItem(
                type="order",
                id=order.id,
                amount=float(order.totalAmount),
                timestamp=order.orderTime,
            )
            for order in today_orders
        ]

        return AdminStatsResponse(
            totalRestaurants=total_restaurants,
            totalOrdersToday=len(today_orders),
            revenueToday=round(revenue_today, 2),
            activeUsers=active_users,
            recentActivity=recent_activity,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error calculating admin stats: {str(e)}",
        )


@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def get_platform_analytics(
    range: AnalyticsRange = Query(AnalyticsRange.week),
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    del current_user
    days_map = {
        AnalyticsRange.day: 1,
        AnalyticsRange.week: 7,
        AnalyticsRange.month: 30,
    }
    start_date = datetime.now() - timedelta(days=days_map[range])

    try:
        orders = await db.order.find_many(
            where={"orderTime": {"gte": start_date}},
            include={
                "restaurant": {"select": {"id": True, "name": True}},
            },
        )

        total_orders = len(orders)
        total_revenue = sum(float(order.totalAmount) for order in orders)
        average_order_value = total_revenue / total_orders if total_orders else 0

        restaurant_metrics = {}
        for order in orders:
            if not order.restaurant:
                continue
            if order.restaurant.id not in restaurant_metrics:
                restaurant_metrics[order.restaurant.id] = {
                    "restaurantId": order.restaurant.id,
                    "restaurantName": order.restaurant.name,
                    "orders": 0,
                    "revenue": 0.0,
                }
            restaurant_metrics[order.restaurant.id]["orders"] += 1
            restaurant_metrics[order.restaurant.id]["revenue"] += float(order.totalAmount)

        top_restaurants = [
            TopRestaurantMetric(
                restaurantId=value["restaurantId"],
                restaurantName=value["restaurantName"],
                orders=value["orders"],
                revenue=round(value["revenue"], 2),
            )
            for value in sorted(
                restaurant_metrics.values(),
                key=lambda item: item["revenue"],
                reverse=True,
            )[:5]
        ]

        return AdminAnalyticsResponse(
            range=range,
            totalOrders=total_orders,
            totalRevenue=round(total_revenue, 2),
            averageOrderValue=round(average_order_value, 2),
            activeRestaurants=len(restaurant_metrics),
            topRestaurants=top_restaurants,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error calculating admin analytics: {str(e)}",
        )


@router.get("/settings", response_model=PlatformSettingsResponse)
async def get_platform_settings(
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    del current_user
    try:
        platform_settings = await _get_or_create_platform_settings(db)
        return PlatformSettingsResponse.model_validate(platform_settings)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching platform settings: {str(e)}",
        )


@router.put("/settings", response_model=PlatformSettingsResponse)
async def update_platform_settings(
    settings_update: PlatformSettingsUpdate,
    current_user=Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    del current_user
    try:
        platform_settings = await _get_or_create_platform_settings(db)

        update_data = settings_update.model_dump(exclude_none=True)
        if not update_data:
            return PlatformSettingsResponse.model_validate(platform_settings)

        updated_settings = await db.platformsettings.update(
            where={"id": platform_settings.id},
            data=update_data,
        )
        return PlatformSettingsResponse.model_validate(updated_settings)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating platform settings: {str(e)}",
        )
