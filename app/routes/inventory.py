from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.inventory import (
    InventoryItemCreate, InventoryItemUpdate, InventoryItemResponse,
    InventoryStockUpdate, InventoryStockUpdateResponse, InventoryStatsResponse,
    InventoryLowStockAlert, InventoryCategoryResponse,
    InventorySupplierResponse
)
from app.middleware.roles import (
    get_current_staff_user
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update as sa_update, delete as sa_delete
from sqlalchemy.orm import selectinload
from app.core.database import get_db_session
from app.models.sqlalchemy_models import Inventory, Ingredient, Restaurant, Dish


router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


# ==================== INVENTORY ITEMS CRUD ====================

@router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    item_data: InventoryItemCreate,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create new inventory item (Manager/Admin only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create inventory items"
        )

    # Check if user can manage this restaurant's inventory
    if current_user.role != "ADMIN" and current_user.restaurantId != item_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage inventory for your own restaurant"
        )

    # Validate restaurant exists
    restaurant = await db.get(Restaurant, item_data.restaurantId)
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )

    # Check if item with same name already exists in this restaurant
    existing_item = (
        await db.execute(
            select(Inventory).where(
                Inventory.restaurantId == item_data.restaurantId,
                Inventory.name == item_data.name,
                Inventory.isActive == True
            )
        )
    ).scalar_one_or_none()

    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inventory item '{item_data.name}' already exists in this restaurant"
        )

    try:
        # Calculate total value
        total_value = item_data.currentStock * item_data.unitPrice

        # Create inventory item
        inventory_item = Inventory(
            restaurantId=item_data.restaurantId,
            name=item_data.name,
            description=item_data.description,
            category=item_data.category,
            unit=item_data.unit,
            currentStock=item_data.currentStock,
            minimumStock=item_data.minimumStock,
            unitPrice=item_data.unitPrice,
            supplier=item_data.supplier,
            location=item_data.location,
            expiryDate=item_data.expiryDate
        )
        db.add(inventory_item)
        await db.commit()
        await db.refresh(inventory_item)

        # Load restaurant relationship
        result = await db.execute(
            select(Inventory).where(Inventory.id == inventory_item.id).options(selectinload(Inventory.restaurant))
        )
        inventory_item = result.scalar_one()

        # Format response
        item_dict = {c.name: getattr(inventory_item, c.name) for c in inventory_item.__table__.columns}
        item_dict["totalValue"] = total_value
        item_dict["isLowStock"] = item_data.currentStock <= item_data.minimumStock
        item_dict["restaurant"] = {"name": inventory_item.restaurant.name} if inventory_item.restaurant else None

        return InventoryItemResponse.model_validate(item_dict)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating inventory item: {str(e)}"
        )


@router.get("/items", response_model=List[InventoryItemResponse])
async def get_inventory_items(
    restaurant_id: int = Query(...),
    category: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    low_stock_only: bool = Query(False),
    expiring_soon: bool = Query(False),
    is_active: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get inventory items with filters (Staff only)."""

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view inventory for your own restaurant"
        )

    # Build where clause
    conditions = [
        Inventory.restaurantId == restaurant_id,
        Inventory.isActive == is_active
    ]

    if category:
        conditions.append(Inventory.category == category)

    if supplier:
        conditions.append(Inventory.supplier == supplier)

    if location:
        conditions.append(Inventory.location == location)

    # Handle expiring soon filter
    if expiring_soon:
        expiry_threshold = datetime.now() + timedelta(days=7)
        conditions.append(Inventory.expiryDate <= expiry_threshold)
        conditions.append(Inventory.expiryDate >= datetime.now())

    try:
        result = await db.execute(
            select(Inventory)
            .where(and_(*conditions))
            .options(selectinload(Inventory.restaurant))
            .order_by(Inventory.name)
            .offset(skip)
            .limit(limit)
        )
        inventory_items = result.scalars().all()

        # Format response and apply low stock filter if needed
        response_items = []
        for item in inventory_items:
            item_dict = {c.name: getattr(item, c.name) for c in item.__table__.columns}
            item_dict["totalValue"] = item.currentStock * item.unitPrice
            item_dict["isLowStock"] = item.currentStock <= item.minimumStock
            item_dict["restaurant"] = {"name": item.restaurant.name} if item.restaurant else None

            # Apply low stock filter
            if low_stock_only and not item_dict["isLowStock"]:
                continue

            response_items.append(InventoryItemResponse.model_validate(item_dict))

        return response_items

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching inventory items: {str(e)}"
        )


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
    item_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get single inventory item (Staff only)."""

    # Get inventory item
    result = await db.execute(
        select(Inventory).where(Inventory.id == item_id).options(selectinload(Inventory.restaurant))
    )
    inventory_item = result.scalar_one_or_none()

    if not inventory_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != inventory_item.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view inventory items from your own restaurant"
        )

    # Format response
    item_dict = {c.name: getattr(inventory_item, c.name) for c in inventory_item.__table__.columns}
    item_dict["totalValue"] = inventory_item.currentStock * inventory_item.unitPrice
    item_dict["isLowStock"] = inventory_item.currentStock <= inventory_item.minimumStock
    item_dict["restaurant"] = {"name": inventory_item.restaurant.name} if inventory_item.restaurant else None

    return InventoryItemResponse.model_validate(item_dict)


@router.put("/items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int,
    item_data: InventoryItemUpdate,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update inventory item (Manager/Admin only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can update inventory items"
        )

    # Get inventory item
    inventory_item = await db.get(Inventory, item_id)

    if not inventory_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    # Check if user can manage this restaurant's inventory
    if current_user.role != "ADMIN" and current_user.restaurantId != inventory_item.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update inventory items from your own restaurant"
        )

    # Prepare update data
    update_data = {}
    for field, value in item_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    try:
        # Update inventory item
        for field, value in update_data.items():
            setattr(inventory_item, field, value)
        await db.commit()
        await db.refresh(inventory_item)

        # Load restaurant relationship
        result = await db.execute(
            select(Inventory).where(Inventory.id == inventory_item.id).options(selectinload(Inventory.restaurant))
        )
        inventory_item = result.scalar_one()

        # Format response
        item_dict = {c.name: getattr(inventory_item, c.name) for c in inventory_item.__table__.columns}
        item_dict["totalValue"] = inventory_item.currentStock * inventory_item.unitPrice
        item_dict["isLowStock"] = inventory_item.currentStock <= inventory_item.minimumStock
        item_dict["restaurant"] = {"name": inventory_item.restaurant.name} if inventory_item.restaurant else None

        return InventoryItemResponse.model_validate(item_dict)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating inventory item: {str(e)}"
        )


@router.delete("/items/{item_id}")
async def delete_inventory_item(
    item_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete (deactivate) inventory item (Manager/Admin only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can delete inventory items"
        )

    # Get inventory item
    inventory_item = await db.get(Inventory, item_id)

    if not inventory_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    # Check if user can manage this restaurant's inventory
    if current_user.role != "ADMIN" and current_user.restaurantId != inventory_item.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete inventory items from your own restaurant"
        )

    try:
        # Soft delete by setting isActive to False
        inventory_item.isActive = False
        await db.commit()

        return {"message": f"Inventory item '{inventory_item.name}' has been deactivated"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting inventory item: {str(e)}"
        )


# ==================== STOCK MANAGEMENT ====================

@router.post("/stock/update", response_model=InventoryStockUpdateResponse)
async def update_stock_quantity(
    stock_update: InventoryStockUpdate,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update stock quantity (add/consume stock) (Staff only)."""

    # Get inventory item
    inventory_item = await db.get(Inventory, stock_update.itemId)

    if not inventory_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != inventory_item.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update stock for your own restaurant's inventory"
        )

    # Calculate new stock quantity
    new_stock = inventory_item.currentStock + stock_update.quantityChange

    # Validate stock won't go negative
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Current: {inventory_item.currentStock}, Requested change: {stock_update.quantityChange}"
        )

    try:
        # Update stock quantity
        inventory_item.currentStock = new_stock
        await db.commit()
        await db.refresh(inventory_item)

        action = "Added" if stock_update.quantityChange > 0 else "Consumed"

        return InventoryStockUpdateResponse(
            success=True,
            previousStock=inventory_item.currentStock - stock_update.quantityChange,
            newStock=new_stock,
            quantityChanged=stock_update.quantityChange,
            message=f"{action} {abs(stock_update.quantityChange)} {inventory_item.unit} of {inventory_item.name}. Reason: {stock_update.reason}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating stock: {str(e)}"
        )


@router.get("/low-stock-alerts/{restaurant_id}", response_model=List[InventoryLowStockAlert])
async def get_low_stock_alerts(
    restaurant_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get low stock alerts for restaurant (Staff only)."""

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view alerts for your own restaurant"
        )

    try:
        # Get items where current stock <= minimum stock
        result = await db.execute(
            select(Inventory).where(
                Inventory.restaurantId == restaurant_id,
                Inventory.isActive == True
            )
        )
        low_stock_items = result.scalars().all()

        # Filter items with low stock
        alerts = []
        for item in low_stock_items:
            if item.currentStock <= item.minimumStock:
                alerts.append(InventoryLowStockAlert.model_validate(item))

        return alerts

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching low stock alerts: {str(e)}"
        )


# ==================== ANALYTICS & REPORTING ====================

@router.get("/stats/{restaurant_id}", response_model=InventoryStatsResponse)
async def get_inventory_stats(
    restaurant_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get inventory statistics for restaurant (Staff only)."""

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view stats for your own restaurant"
        )

    # Get restaurant name
    restaurant = await db.get(Restaurant, restaurant_id)

    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    try:
        # Get all inventory items
        result = await db.execute(
            select(Inventory).where(Inventory.restaurantId == restaurant_id)
        )
        all_items = result.scalars().all()

        active_items = [item for item in all_items if item.isActive]
        low_stock_items = [item for item in active_items if item.currentStock <= item.minimumStock]

        # Items expiring in next 7 days
        expiry_threshold = datetime.now() + timedelta(days=7)
        expiring_soon_items = [
            item for item in active_items
            if item.expiryDate and item.expiryDate <= expiry_threshold and item.expiryDate >= datetime.now()
        ]

        # Calculate total value
        total_value = sum(item.currentStock * item.unitPrice for item in active_items)
        average_item_value = total_value / len(active_items) if active_items else 0

        # Count unique categories and suppliers
        categories = set(item.category for item in active_items if item.category)
        suppliers = set(item.supplier for item in active_items if item.supplier)

        return InventoryStatsResponse(
            restaurantId=restaurant_id,
            restaurantName=restaurant.name,
            totalItems=len(all_items),
            activeItems=len(active_items),
            lowStockItems=len(low_stock_items),
            totalValue=round(total_value, 2),
            averageItemValue=round(average_item_value, 2),
            expiringSoonItems=len(expiring_soon_items),
            categoriesCount=len(categories),
            suppliersCount=len(suppliers)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error calculating inventory stats: {str(e)}"
        )


@router.get("/categories/{restaurant_id}", response_model=List[InventoryCategoryResponse])
async def get_inventory_by_category(
    restaurant_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get inventory breakdown by category (Staff only)."""

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view categories for your own restaurant"
        )

    try:
        # Get all active inventory items
        result = await db.execute(
            select(Inventory).where(
                Inventory.restaurantId == restaurant_id,
                Inventory.isActive == True
            )
        )
        items = result.scalars().all()

        # Group by category
        category_data = {}
        for item in items:
            category = item.category or "Uncategorized"

            if category not in category_data:
                category_data[category] = {
                    "category": category,
                    "itemCount": 0,
                    "totalValue": 0,
                    "lowStockCount": 0
                }

            category_data[category]["itemCount"] += 1
            category_data[category]["totalValue"] += item.currentStock * item.unitPrice

            if item.currentStock <= item.minimumStock:
                category_data[category]["lowStockCount"] += 1

        # Convert to response format
        result_list = []
        for data in category_data.values():
            data["totalValue"] = round(data["totalValue"], 2)
            result_list.append(InventoryCategoryResponse.model_validate(data))

        return sorted(result_list, key=lambda x: x.totalValue, reverse=True)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching category breakdown: {str(e)}"
        )


@router.get("/suppliers/{restaurant_id}", response_model=List[InventorySupplierResponse])
async def get_inventory_by_supplier(
    restaurant_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get inventory breakdown by supplier (Staff only)."""

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view suppliers for your own restaurant"
        )

    try:
        # Get all active inventory items
        result = await db.execute(
            select(Inventory).where(
                Inventory.restaurantId == restaurant_id,
                Inventory.isActive == True
            )
        )
        items = result.scalars().all()

        # Group by supplier
        supplier_data = {}
        for item in items:
            supplier = item.supplier or "Unknown Supplier"

            if supplier not in supplier_data:
                supplier_data[supplier] = {
                    "supplier": supplier,
                    "itemCount": 0,
                    "totalValue": 0,
                    "lowStockCount": 0
                }

            supplier_data[supplier]["itemCount"] += 1
            supplier_data[supplier]["totalValue"] += item.currentStock * item.unitPrice

            if item.currentStock <= item.minimumStock:
                supplier_data[supplier]["lowStockCount"] += 1

        # Convert to response format
        result_list = []
        for data in supplier_data.values():
            data["totalValue"] = round(data["totalValue"], 2)
            result_list.append(InventorySupplierResponse.model_validate(data))

        return sorted(result_list, key=lambda x: x.totalValue, reverse=True)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching supplier breakdown: {str(e)}"
        )
