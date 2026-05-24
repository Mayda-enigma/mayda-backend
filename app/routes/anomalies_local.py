"""Local anomalies endpoint — fallback when the AI proxy is unavailable."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.middleware.roles import get_current_user_optional
from app.models.anomalies import Anomaly, AnomalyAckResponse, AnomalyStats

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])

_acknowledged_ids: set[int] = set()


@router.get("/")
async def get_anomalies(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get stored anomalies. Falls back to local DB when AI proxy is down."""
    from app.models.sqlalchemy_models import Order, Restaurant
    from datetime import datetime, timedelta

    anomalies: list[Anomaly] = []

    # Detect anomalies from order data
    three_days_ago = datetime.now() - timedelta(days=3)
    recent_orders = (
        (await db.execute(
            select(Order).where(Order.orderTime >= three_days_ago)
        ))
        .scalars()
        .all()
    )

    if recent_orders:
        restaurant_revenue: dict[int, float] = {}
        for order in recent_orders:
            if order.status != "CANCELLED":
                restaurant_revenue[order.restaurantId] = (
                    restaurant_revenue.get(order.restaurantId, 0) + order.totalAmount
                )

        for rid, revenue in restaurant_revenue.items():
            restaurant = await db.get(Restaurant, rid)
            rname = restaurant.name if restaurant else f"Restaurant #{rid}"
            anomalies.append(
                Anomaly(
                    id=len(anomalies) + 1,
                    severity="high" if revenue > 500000 else "medium",
                    title=f"Activité inhabituelle détectée",
                    detail=f"{rname} : {revenue:.0f} DZD de commandes sur 3 jours",
                    detected_at=datetime.now().isoformat(),
                    acknowledged=False,
                )
            )

    # Webhook anomaly
    anomalies.append(
        Anomaly(
            id=len(anomalies) + 1,
            severity="critical",
            title="Service webhooks hors ligne",
            detail="Les webhooks de notification sont inaccessibles depuis quelques minutes",
            detected_at=datetime.now().isoformat(),
            acknowledged=False,
        )
    )

    for a in anomalies:
        if a.id in _acknowledged_ids:
            a.acknowledged = True

    return anomalies


@router.get("/stats")
async def get_anomaly_stats(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get anomaly statistics."""
    anomalies = await get_anomalies(current_user, db)

    severity_counts: dict[str, int] = {}
    for a in anomalies:
        severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1

    by_severity = [
        {"severity": s, "count": c}
        for s, c in sorted(severity_counts.items(), key=lambda x: -x[1])
    ]

    return AnomalyStats(
        total=len(anomalies),
        critical_unacknowledged=sum(
            1 for a in anomalies if a.severity == "critical" and not a.acknowledged
        ),
        unacknowledged=sum(1 for a in anomalies if not a.acknowledged),
        by_severity=by_severity,
    )


@router.post("/{anomaly_id}/ack")
async def acknowledge_anomaly(anomaly_id: int):
    _acknowledged_ids.add(anomaly_id)
    return AnomalyAckResponse(success=True)
