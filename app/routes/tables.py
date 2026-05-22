from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.models.table import (
    TableCreate, TableUpdate, TableResponse, TableListResponse
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_manager_or_admin, get_current_staff_user,
    get_current_user_optional
)


router = APIRouter(prefix="/tables", tags=["Tables"])


@router.get("/restaurant/{restaurant_id}", response_model=List[TableListResponse])
async def get_restaurant_tables(
    restaurant_id: int,
    active_only: bool = Query(True),
    current_user = Depends(get_current_user_optional)
):
    """Get tables for a restaurant (public endpoint for customers to see available tables)."""
    db = get_db()
    
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
    current_user = Depends(get_current_user_optional)
):
    """Get table by ID (public endpoint)."""
    db = get_db()
    
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
    current_user = Depends(get_current_manager_or_admin)
):
    """Create a new table (Manager/Admin only). Managers can only create tables for their restaurant."""
    db = get_db()
    
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
    current_user = Depends(get_current_manager_or_admin)
):
    """Update table (Manager/Admin only). Managers can only update tables in their restaurant."""
    db = get_db()
    
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
    current_user = Depends(get_current_manager_or_admin)
):
    """Delete table (Manager/Admin only). Managers can only delete tables from their restaurant."""
    db = get_db()
    
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
    current_user = Depends(get_current_staff_user)
):
    """Toggle table active status (Staff only - for their restaurant)."""
    db = get_db()
    
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


@router.get("/{table_id}/current-orders")
async def get_table_current_orders(
    table_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Get current orders for a table (Staff only)."""
    db = get_db()
    
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
    current_user = Depends(get_current_user_optional)
):
    """Get table availability status for a restaurant (public endpoint for customers)."""
    db = get_db()
    
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
        availability.append({
            "id": table.id,
            "number": table.number,
            "capacity": table.capacity,
            "qrCode": table.qrCode,
            "isOccupied": has_active_orders,
            "activeOrders": len(table.orders)
        })
    
    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.name,
        "tables": availability,
        "total_tables": len(availability),
        "available_tables": len([t for t in availability if not t["isOccupied"]])
    }
