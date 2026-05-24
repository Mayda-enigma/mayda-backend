from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.middleware.roles import get_current_user_optional
from app.models.admin_dashboard import (
    ActivityItem,
    ChannelData,
    InfraService,
    PeakHour,
    RevenuePoint,
    TopRestaurant,
)
from app.models.sqlalchemy_models import Order, Restaurant

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


@router.get("/revenue")
async def get_revenue_trend(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    thirty_days_ago = datetime.now() - timedelta(days=30)
    orders = (
        (
            await db.execute(
                select(Order)
                .where(
                    Order.orderTime >= thirty_days_ago,
                    Order.status != "CANCELLED",
                )
                .order_by(Order.orderTime.asc())
            )
        )
        .scalars()
        .all()
    )

    daily: dict[str, float] = {}
    for i in range(31):
        date = (datetime.now() - timedelta(days=30 - i)).strftime("%Y-%m-%d")
        daily[date] = 0.0

    for order in orders:
        ot = order.orderTime
        date = ot.strftime("%Y-%m-%d") if hasattr(ot, "strftime") else str(ot)[:10]
        if date in daily:
            daily[date] += order.totalAmount

    return [RevenuePoint(date=d, amount=round(a, 2)) for d, a in daily.items()]


@router.get("/channels")
async def get_order_channels(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    orders = (
        (
            await db.execute(
                select(Order).where(Order.orderTime >= today_start)
            )
        )
        .scalars()
        .all()
    )

    counts: dict[str, int] = defaultdict(int)
    for order in orders:
        counts[order.type.value] += 1

    channel_labels = {
        "DINE_IN": "Sur place",
        "TAKEAWAY": "À emporter",
        "DELIVERY": "Livraison",
    }

    return [
        ChannelData(channel=channel_labels.get(k, k), count=v)
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


@router.get("/peak-hours")
async def get_peak_hours(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    last_7_days = datetime.now() - timedelta(days=7)
    orders = (
        (
            await db.execute(
                select(Order).where(Order.orderTime >= last_7_days)
            )
        )
        .scalars()
        .all()
    )

    hourly: dict[int, int] = defaultdict(int)
    for order in orders:
        hour = order.orderTime.hour
        hourly[hour] += 1

    return [
        PeakHour(hour=h, order_count=hourly.get(h, 0))
        for h in range(24)
    ]


@router.get("/top-restaurants")
async def get_top_restaurants(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    orders = (await db.execute(select(Order).where(Order.status != "CANCELLED"))).scalars().all()

    totals: dict[int, float] = defaultdict(float)
    for order in orders:
        totals[order.restaurantId] += order.totalAmount

    sorted_ids = sorted(totals.items(), key=lambda x: -x[1])[:5]

    rids = [rid for rid, _ in sorted_ids]
    restaurants = (
        (
            await db.execute(
                select(Restaurant)
                .options(selectinload(Restaurant.address))
                .where(Restaurant.id.in_(rids))
            )
        )
        .scalars()
        .all()
    )
    rest_map = {r.id: r for r in restaurants}

    result = []
    for rid, revenue in sorted_ids:
        restaurant = rest_map.get(rid)
        if restaurant:
            addr = restaurant.address if restaurant.address else None
            result.append(
                TopRestaurant(
                    name=restaurant.name,
                    city=addr.city if addr else "N/A",
                    revenue=round(revenue, 2),
                )
            )

    return result


@router.get("/activity")
async def get_recent_activity(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    recent_orders = (
        (
            await db.execute(
                select(Order)
                .options(selectinload(Order.restaurant))
                .order_by(Order.orderTime.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    items = []
    for order in recent_orders:
        items.append(
            ActivityItem(
                label=f"Nouvelle commande #{order.orderNumber}",
                meta=(
                    f"{order.restaurant.name} · {order.totalAmount} DZD"
                    if order.restaurant
                    else f"{order.totalAmount} DZD"
                ),
                created_at=order.orderTime.isoformat(),
            )
        )

    return items


@router.get("/infra-health")
async def get_infra_health(
    current_user=Depends(get_current_user_optional),
):
    return [
        InfraService(service="Base de données", status="healthy", latency_ms=3.2, uptime_pct=99.97),
        InfraService(service="Serveurs API", status="healthy", latency_ms=12.5, uptime_pct=99.99),
        InfraService(service="Webhooks", status="degraded", latency_ms=245.0, uptime_pct=98.50),
        InfraService(service="Services tiers", status="healthy", latency_ms=45.0, uptime_pct=99.80),
        InfraService(service="Cache Redis", status="healthy", latency_ms=1.1, uptime_pct=100.0),
    ]
