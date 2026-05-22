from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.inventory import (
    InventoryItemCreate, InventoryItemUpdate, InventoryItemResponse,
    InventoryStockUpdate, InventoryStockUpdateResponse, InventoryStatsResponse,
    InventoryLowStockAlert, InventorySearchFilters, InventoryCategoryResponse,
    InventorySupplierResponse
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_staff_user, get_admin_user, get_manager_user
)


router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


# ==================== INVENTORY ITEMS CRUD ====================

@router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    item_data: InventoryItemCreate,
    current_user = Depends(get_current_staff_user)
):
    """Create new inventory item (Manager/Admin only)."""
    db = get_db()
    
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
    restaurant = await db.restaurant.find_unique(
        where={"id": item_data.restaurantId}
    )
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Check if item with same name already exists in this restaurant
    existing_item = await db.inventory.find_first(
        where={
            "restaurantId": item_data.restaurantId,
            "name": item_data.name,
            "isActive": True
        }
    )
    
    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inventory item '{item_data.name}' already exists in this restaurant"
        )
    
    try:
        # Calculate total value
        total_value = item_data.currentStock * item_data.unitPrice
        
        # Create inventory item
        inventory_item = await db.inventory.create(
            data={
                "restaurantId": item_data.restaurantId,
                "name": item_data.name,
                "description": item_data.description,
                "category": item_data.category,
                "unit": item_data.unit,
                "currentStock": item_data.currentStock,
                "minimumStock": item_data.minimumStock,
                "unitPrice": item_data.unitPrice,
                "supplier": item_data.supplier,
                "location": item_data.location,
                "expiryDate": item_data.expiryDate
            },
            include={
                "restaurant": {
                    "select": {
                        "name": True
                    }
                }
            }
        )
        
        # Format response
        item_dict = inventory_item.__dict__.copy()
        item_dict["totalValue"] = total_value
        item_dict["isLowStock"] = item_data.currentStock <= item_data.minimumStock
        
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
    current_user = Depends(get_current_staff_user)
):
    """Get inventory items with filters (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view inventory for your own restaurant"
        )
    
    # Build where clause
    where_clause = {
        "restaurantId": restaurant_id,
        "isActive": is_active
    }
    
    if category:
        where_clause["category"] = category
    
    if supplier:
        where_clause["supplier"] = supplier
    
    if location:
        where_clause["location"] = location
    
    # Handle expiring soon filter
    if expiring_soon:
        expiry_threshold = datetime.now() + timedelta(days=7)
        where_clause["expiryDate"] = {
            "lte": expiry_threshold,
            "gte": datetime.now()
        }
    
    try:
        inventory_items = await db.inventory.find_many(
            where=where_clause,
            include={
                "restaurant": {
                    "select": {
                        "name": True
                    }
                }
            },
            skip=skip,
            take=limit,
            order={"name": "asc"}
        )
        
        # Format response and apply low stock filter if needed
        result = []
        for item in inventory_items:
            item_dict = item.__dict__.copy()
            item_dict["totalValue"] = item.currentStock * item.unitPrice
            item_dict["isLowStock"] = item.currentStock <= item.minimumStock
            
            # Apply low stock filter
            if low_stock_only and not item_dict["isLowStock"]:
                continue
                
            result.append(InventoryItemResponse.model_validate(item_dict))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching inventory items: {str(e)}"
        )


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
    item_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Get single inventory item (Staff only)."""
    db = get_db()
    
    # Get inventory item
    inventory_item = await db.inventory.find_unique(
        where={"id": item_id},
        include={
            "restaurant": {
                "select": {
                    "name": True
                }
            }
        }
    )
    
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
    item_dict = inventory_item.__dict__.copy()
    item_dict["totalValue"] = inventory_item.currentStock * inventory_item.unitPrice
    item_dict["isLowStock"] = inventory_item.currentStock <= inventory_item.minimumStock
    
    return InventoryItemResponse.model_validate(item_dict)


@router.put("/items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int,
    item_data: InventoryItemUpdate,
    current_user = Depends(get_current_staff_user)
):
    """Update inventory item (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can update inventory items"
        )
    
    # Get inventory item
    inventory_item = await db.inventory.find_unique(
        where={"id": item_id}
    )
    
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
        updated_item = await db.inventory.update(
            where={"id": item_id},
            data=update_data,
            include={
                "restaurant": {
                    "select": {
                        "name": True
                    }
                }
            }
        )
        
        # Format response
        item_dict = updated_item.__dict__.copy()
        item_dict["totalValue"] = updated_item.currentStock * updated_item.unitPrice
        item_dict["isLowStock"] = updated_item.currentStock <= updated_item.minimumStock
        
        return InventoryItemResponse.model_validate(item_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating inventory item: {str(e)}"
        )


@router.delete("/items/{item_id}")
async def delete_inventory_item(
    item_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Delete (deactivate) inventory item (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can delete inventory items"
        )
    
    # Get inventory item
    inventory_item = await db.inventory.find_unique(
        where={"id": item_id}
    )
    
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
        await db.inventory.update(
            where={"id": item_id},
            data={"isActive": False}
        )
        
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
    current_user = Depends(get_current_staff_user)
):
    """Update stock quantity (add/consume stock) (Staff only)."""
    db = get_db()
    
    # Get inventory item
    inventory_item = await db.inventory.find_unique(
        where={"id": stock_update.itemId}
    )
    
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
        await db.inventory.update(
            where={"id": stock_update.itemId},
            data={"currentStock": new_stock}
        )
        
        # Create stock transaction log (if you want to track stock changes)
        # This could be a separate StockTransaction model for audit trail
        
        action = "Added" if stock_update.quantityChange > 0 else "Consumed"
        
        return InventoryStockUpdateResponse(
            success=True,
            previousStock=inventory_item.currentStock,
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
    current_user = Depends(get_current_staff_user)
):
    """Get low stock alerts for restaurant (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view alerts for your own restaurant"
        )
    
    try:
        # Get items where current stock <= minimum stock
        low_stock_items = await db.inventory.find_many(
            where={
                "restaurantId": restaurant_id,
                "isActive": True
            }
        )
        
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
    current_user = Depends(get_current_staff_user)
):
    """Get inventory statistics for restaurant (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view stats for your own restaurant"
        )
    
    # Get restaurant name
    restaurant = await db.restaurant.find_unique(
        where={"id": restaurant_id}
    )
    
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    try:
        # Get all inventory items
        all_items = await db.inventory.find_many(
            where={"restaurantId": restaurant_id}
        )
        
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
    current_user = Depends(get_current_staff_user)
):
    """Get inventory breakdown by category (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view categories for your own restaurant"
        )
    
    try:
        # Get all active inventory items
        items = await db.inventory.find_many(
            where={
                "restaurantId": restaurant_id,
                "isActive": True
            }
        )
        
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
        result = []
        for data in category_data.values():
            data["totalValue"] = round(data["totalValue"], 2)
            result.append(InventoryCategoryResponse.model_validate(data))
        
        return sorted(result, key=lambda x: x.totalValue, reverse=True)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching category breakdown: {str(e)}"
        )


@router.get("/suppliers/{restaurant_id}", response_model=List[InventorySupplierResponse])
async def get_inventory_by_supplier(
    restaurant_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Get inventory breakdown by supplier (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view suppliers for your own restaurant"
        )
    
    try:
        # Get all active inventory items
        items = await db.inventory.find_many(
            where={
                "restaurantId": restaurant_id,
                "isActive": True
            }
        )
        
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
        result = []
        for data in supplier_data.values():
            data["totalValue"] = round(data["totalValue"], 2)
            result.append(InventorySupplierResponse.model_validate(data))
        
        return sorted(result, key=lambda x: x.totalValue, reverse=True)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching supplier breakdown: {str(e)}"
        )
