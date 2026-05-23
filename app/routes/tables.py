from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.middleware.roles import (
    get_current_manager_or_admin,
    get_current_staff_user,
    get_current_user_optional,
)
from app.models.sqlalchemy_models import (
    Order,
    OrderItem,
    Restaurant,
    Table,
    TableSession,
)
from app.models.table import (
    CurrentOccupantInfo,
    TableCheckinResponse,
    TableCreate,
    TableListResponse,
    TableResponse,
    TableStatus,
    TableUpdate,
)

router = APIRouter(prefix="/tables", tags=["Tables"])


def build_current_occupant_info(session) -> CurrentOccupantInfo:
    waiter_name = f"{session.waiter.firstName} {session.waiter.lastName}".strip() if session.waiter else "Unknown"
    return CurrentOccupantInfo(
        sessionId=session.id,
        waiterId=session.waiterId,
        waiterName=waiter_name,
        startedAt=session.startedAt,
    )


@router.get("/restaurant/{restaurant_id}", response_model=list[TableListResponse])
async def get_restaurant_tables(
    restaurant_id: int,
    active_only: bool = Query(True),
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get tables for a restaurant (public endpoint for customers to see available tables)."""

    restaurant = await db.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    where_conditions = [Table.restaurantId == restaurant_id]
    if active_only:
        where_conditions.append(Table.isActive == True)

    tables = (
        (await db.execute(select(Table).where(and_(*where_conditions)).order_by(Table.number.asc()))).scalars().all()
    )

    return [TableListResponse.model_validate(table) for table in tables]


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: int,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get table by ID (public endpoint)."""

    table = await db.get(Table, table_id)

    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    return TableResponse.model_validate(table)


@router.post("/", response_model=TableResponse)
async def create_table(
    table_data: TableCreate,
    current_user=Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new table (Manager/Admin only). Managers can only create tables for their restaurant."""

    restaurant = await db.get(Restaurant, table_data.restaurantId)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    if current_user.role != "ADMIN" and current_user.restaurantId != table_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create tables for your own restaurant",
        )

    existing_table = (
        await db.execute(
            select(Table).where(
                and_(
                    Table.restaurantId == table_data.restaurantId,
                    Table.number == table_data.number,
                )
            )
        )
    ).scalar_one_or_none()

    if existing_table:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table number {table_data.number} already exists in this restaurant",
        )

    try:
        table = Table(
            restaurantId=table_data.restaurantId,
            number=table_data.number,
            capacity=table_data.capacity,
            isActive=table_data.isActive,
            status=table_data.status.value,
            qrCode=table_data.qrCode,
            nfcTag=table_data.nfcTag,
        )
        db.add(table)
        await db.commit()
        await db.refresh(table)

        return TableResponse.model_validate(table)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating table: {str(e)}",
        )


@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_data: TableUpdate,
    current_user=Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Update table (Manager/Admin only). Managers can only update tables in their restaurant."""

    table = await db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update tables in your own restaurant",
        )

    if table_data.number and table_data.number != table.number:
        existing_table = (
            await db.execute(
                select(Table).where(
                    and_(
                        Table.restaurantId == table.restaurantId,
                        Table.number == table_data.number,
                        Table.id != table_id,
                    )
                )
            )
        ).scalar_one_or_none()

        if existing_table:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table number {table_data.number} already exists in this restaurant",
            )

    update_data = {}
    for field, value in table_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value

    if "status" in update_data:
        update_data["status"] = update_data["status"].value

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    try:
        for field, value in update_data.items():
            setattr(table, field, value)
        await db.commit()
        await db.refresh(table)

        return TableResponse.model_validate(table)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating table: {str(e)}",
        )


@router.delete("/{table_id}")
async def delete_table(
    table_id: int,
    current_user=Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete table (Manager/Admin only). Managers can only delete tables from their restaurant."""

    table = await db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete tables from your own restaurant",
        )

    active_orders = (
        await db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.tableId == table_id,
                    Order.status.in_(["PENDING", "CONFIRMED", "PREPARING", "READY"]),
                )
            )
        )
    ).scalar()

    if active_orders > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete table with active orders",
        )

    try:
        await db.delete(table)
        await db.commit()
        return {"message": f"Table {table.number} deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting table: {str(e)}",
        )


@router.patch("/{table_id}/toggle-status")
async def toggle_table_status(
    table_id: int,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Toggle table active status (Staff only - for their restaurant)."""

    table = await db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage tables in your own restaurant",
        )

    try:
        table.isActive = not table.isActive
        await db.commit()
        await db.refresh(table)

        return {
            "message": f"Table {table.number} {'activated' if table.isActive else 'deactivated'} successfully",
            "table": TableResponse.model_validate(table),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating table status: {str(e)}",
        )


@router.post("/{table_id}/checkin", response_model=TableCheckinResponse)
async def check_in_table(
    table_id: int,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Open a table session after a QR scan (Waiter/Manager/Admin only)."""

    if current_user.role not in ["WAITER", "MANAGER", "ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Waiter access required")

    table = await db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check in tables from your own restaurant",
        )

    if not table.isActive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive tables cannot be checked in",
        )

    active_session = (
        await db.execute(
            select(TableSession)
            .where(and_(TableSession.tableId == table_id, TableSession.isActive == True))
            .options(selectinload(TableSession.waiter))
        )
    ).scalar_one_or_none()

    if table.status.value == TableStatus.OCCUPIED.value or active_session:
        occupant_info = build_current_occupant_info(active_session) if active_session else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Table is already occupied",
                "tableId": table.id,
                "status": table.status.value,
                "currentOccupant": occupant_info.model_dump() if occupant_info else None,
            },
        )

    session = TableSession(
        tableId=table.id,
        waiterId=current_user.id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    table.status = TableStatus.OCCUPIED.value
    await db.commit()
    await db.refresh(table)

    return TableCheckinResponse(
        tableId=table.id,
        status=TableStatus(table.status.value),
        sessionId=session.id,
    )


@router.get("/{table_id}/current-orders")
async def get_table_current_orders(
    table_id: int,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get current orders for a table (Staff only)."""

    table = await db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view orders for tables in your own restaurant",
        )

    orders = (
        (
            await db.execute(
                select(Order)
                .where(
                    and_(
                        Order.tableId == table_id,
                        Order.status.in_(["PENDING", "CONFIRMED", "PREPARING", "READY"]),
                    )
                )
                .options(
                    selectinload(Order.items).selectinload(OrderItem.dish),
                    selectinload(Order.user),
                )
                .order_by(Order.orderTime.desc())
            )
        )
        .scalars()
        .all()
    )

    return {
        "table_id": table_id,
        "table_number": table.number,
        "current_orders": orders,
        "total_orders": len(orders),
    }


@router.get("/restaurant/{restaurant_id}/availability")
async def get_tables_availability(
    restaurant_id: int,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get table availability status for a restaurant (public endpoint for customers)."""

    restaurant = await db.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    tables = (
        (
            await db.execute(
                select(Table)
                .where(and_(Table.restaurantId == restaurant_id, Table.isActive == True))
                .order_by(Table.number.asc())
            )
        )
        .scalars()
        .all()
    )

    active_statuses = ["PENDING", "CONFIRMED", "PREPARING", "READY"]
    if tables:
        count_result = (
            await db.execute(
                select(Order.tableId, func.count(Order.id))
                .where(
                    and_(
                        Order.tableId.in_([t.id for t in tables]),
                        Order.status.in_(active_statuses),
                    )
                )
                .group_by(Order.tableId)
            )
        ).all()
        order_counts = {row[0]: row[1] for row in count_result}
    else:
        order_counts = {}

    availability = []
    for table in tables:
        count = order_counts.get(table.id, 0)
        has_active_orders = count > 0
        is_occupied = table.status.value == TableStatus.OCCUPIED.value or has_active_orders
        availability.append(
            {
                "id": table.id,
                "number": table.number,
                "capacity": table.capacity,
                "status": table.status.value,
                "qrCode": table.qrCode,
                "isOccupied": is_occupied,
                "activeOrders": count,
            }
        )

    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.name,
        "tables": availability,
        "total_tables": len(availability),
        "available_tables": len([t for t in availability if not t["isOccupied"]]),
    }
