from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List
from app.models.table import (
    CurrentOccupantInfo, TableCheckinResponse, TableCreate,
    TableResponse, TableListResponse, TableStatus, TableUpdate
)
from app.core.database import get_db_session
from app.middleware.roles import (
    get_current_manager_or_admin, get_current_staff_user,
    get_current_user_optional
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


@router.get("/restaurant/{restaurant_id}", response_model=List[TableListResponse])
async def get_restaurant_tables(
    restaurant_id: int,
    active_only: bool = Query(True),
    current_user = Depends(get_current_user_optional),
    db: "Prisma" = Depends(get_db_session),
):
    """Get tables for a restaurant (public endpoint for customers to see available tables)."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    where_clause = {"restaurantId": restaurant_id}
    if active_only:
        where_clause["isActive"] = True
    
    tables = await db.table.find_many(
        where=where_clause,
        order={"number": "asc"}
    )
    
    return [TableListResponse.model_validate(table) for table in tables]


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: int,
    current_user = Depends(get_current_user_optional),
    db: "Prisma" = Depends(get_db_session),
):
    """Get table by ID (public endpoint)."""
    
    table = await db.table.find_unique(where={"id": table_id})
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    return TableResponse.model_validate(table)


@router.post("/", response_model=TableResponse)
async def create_table(
    table_data: TableCreate,
    current_user = Depends(get_current_manager_or_admin),
    db: "Prisma" = Depends(get_db_session),
):
    """Create a new table (Manager/Admin only). Managers can only create tables for their restaurant."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": table_data.restaurantId})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions - managers can only create tables for their own restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != table_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create tables for your own restaurant"
        )
    
    # Check if table number already exists in this restaurant
    existing_table = await db.table.find_first(
        where={
            "restaurantId": table_data.restaurantId,
            "number": table_data.number
        }
    )
    
    if existing_table:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table number {table_data.number} already exists in this restaurant"
        )
    
    try:
        table = await db.table.create(
            data={
                "restaurantId": table_data.restaurantId,
                "number": table_data.number,
                "capacity": table_data.capacity,
                "isActive": table_data.isActive,
                "status": table_data.status.value,
                "qrCode": table_data.qrCode,
                "nfcTag": table_data.nfcTag
            }
        )
        
        return TableResponse.model_validate(table)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating table: {str(e)}"
        )


@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_data: TableUpdate,
    current_user = Depends(get_current_manager_or_admin),
    db: "Prisma" = Depends(get_db_session),
):
    """Update table (Manager/Admin only). Managers can only update tables in their restaurant."""
    
    # Check if table exists
    table = await db.table.find_unique(where={"id": table_id})
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check permissions - managers can only update tables in their own restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update tables in your own restaurant"
        )
    
    # If updating table number, check for conflicts
    if table_data.number and table_data.number != table.number:
        existing_table = await db.table.find_first(
            where={
                "restaurantId": table.restaurantId,
                "number": table_data.number,
                "id": {"not": table_id}
            }
        )
        
        if existing_table:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table number {table_data.number} already exists in this restaurant"
            )
    
    # Prepare update data
    update_data = {}
    for field, value in table_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value

    if "status" in update_data:
        update_data["status"] = update_data["status"].value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    try:
        updated_table = await db.table.update(
            where={"id": table_id},
            data=update_data
        )
        
        return TableResponse.model_validate(updated_table)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating table: {str(e)}"
        )


@router.delete("/{table_id}")
async def delete_table(
    table_id: int,
    current_user = Depends(get_current_manager_or_admin),
    db: "Prisma" = Depends(get_db_session),
):
    """Delete table (Manager/Admin only). Managers can only delete tables from their restaurant."""
    
    # Check if table exists
    table = await db.table.find_unique(where={"id": table_id})
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete tables from your own restaurant"
        )
    
    # Check if table has active orders or reservations
    active_orders = await db.order.count(
        where={
            "tableId": table_id,
            "status": {"in": ["PENDING", "CONFIRMED", "PREPARING", "READY"]}
        }
    )
    
    if active_orders > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete table with active orders"
        )
    
    try:
        await db.table.delete(where={"id": table_id})
        return {"message": f"Table {table.number} deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting table: {str(e)}"
        )


@router.patch("/{table_id}/toggle-status")
async def toggle_table_status(
    table_id: int,
    current_user = Depends(get_current_staff_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Toggle table active status (Staff only - for their restaurant)."""
    
    # Check if table exists
    table = await db.table.find_unique(where={"id": table_id})
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check permissions - staff can only manage tables in their own restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage tables in your own restaurant"
        )
    
    try:
        updated_table = await db.table.update(
            where={"id": table_id},
            data={"isActive": not table.isActive}
        )
        
        return {
            "message": f"Table {table.number} {'activated' if updated_table.isActive else 'deactivated'} successfully",
            "table": TableResponse.model_validate(updated_table)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating table status: {str(e)}"
        )


@router.post("/{table_id}/checkin", response_model=TableCheckinResponse)
async def check_in_table(
    table_id: int,
    current_user = Depends(get_current_staff_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Open a table session after a QR scan (Waiter/Manager/Admin only)."""

    if current_user.role not in ["WAITER", "MANAGER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Waiter access required"
        )

    table = await db.table.find_unique(where={"id": table_id})
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check in tables from your own restaurant"
        )

    if not table.isActive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive tables cannot be checked in"
        )

    active_session = await db.tablesession.find_first(
        where={"tableId": table_id, "isActive": True},
        include={
            "waiter": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                }
            }
        }
    )

    if table.status == TableStatus.OCCUPIED.value or active_session:
        occupant_info = build_current_occupant_info(active_session) if active_session else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Table is already occupied",
                "tableId": table.id,
                "status": table.status,
                "currentOccupant": occupant_info.model_dump() if occupant_info else None,
            }
        )

    session = await db.tablesession.create(
        data={
            "tableId": table.id,
            "waiterId": current_user.id,
        }
    )

    updated_table = await db.table.update(
        where={"id": table_id},
        data={"status": TableStatus.OCCUPIED.value},
    )

    return TableCheckinResponse(
        tableId=updated_table.id,
        status=TableStatus(updated_table.status),
        sessionId=session.id,
    )


@router.get("/{table_id}/current-orders")
async def get_table_current_orders(
    table_id: int,
    current_user = Depends(get_current_staff_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Get current orders for a table (Staff only)."""
    
    # Check if table exists
    table = await db.table.find_unique(where={"id": table_id})
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view orders for tables in your own restaurant"
        )
    
    # Get current orders for this table
    orders = await db.order.find_many(
        where={
            "tableId": table_id,
            "status": {"in": ["PENDING", "CONFIRMED", "PREPARING", "READY"]}
        },
        include={
            "items": {
                "include": {"dish": True}
            },
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                    "phone": True
                }
            }
        },
        order={"orderTime": "desc"}
    )
    
    return {
        "table_id": table_id,
        "table_number": table.number,
        "current_orders": orders,
        "total_orders": len(orders)
    }


@router.get("/restaurant/{restaurant_id}/availability")
async def get_tables_availability(
    restaurant_id: int,
    current_user = Depends(get_current_user_optional),
    db: "Prisma" = Depends(get_db_session),
):
    """Get table availability status for a restaurant (public endpoint for customers)."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Get all active tables with their current order status
    tables = await db.table.find_many(
        where={
            "restaurantId": restaurant_id,
            "isActive": True
        },
        include={
            "orders": {
                "where": {
                    "status": {"in": ["PENDING", "CONFIRMED", "PREPARING", "READY"]}
                },
                "select": {
                    "id": True,
                    "status": True,
                    "orderTime": True
                }
            }
        },
        order={"number": "asc"}
    )
    
    # Format availability data
    availability = []
    for table in tables:
        has_active_orders = len(table.orders) > 0
        is_occupied = table.status == TableStatus.OCCUPIED.value or has_active_orders
        availability.append({
            "id": table.id,
            "number": table.number,
            "capacity": table.capacity,
            "status": table.status,
            "qrCode": table.qrCode,
            "isOccupied": is_occupied,
            "activeOrders": len(table.orders)
        })
    
    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.name,
        "tables": availability,
        "total_tables": len(availability),
        "available_tables": len([t for t in availability if not t["isOccupied"]])
    }
