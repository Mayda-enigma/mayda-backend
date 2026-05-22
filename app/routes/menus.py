from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.models.menu import (
    MenuCreate, MenuUpdate, MenuResponse,
    MenuCategoryCreate, MenuCategoryUpdate, MenuCategoryResponse,
    DishCreate, DishUpdate, DishResponse, DishListResponse,
    MenuWithCategories, MenuCategoryWithDishes
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_manager_or_admin, get_current_staff_user,
    get_current_user_optional
)


router = APIRouter(prefix="/menus", tags=["Menus & Dishes"])


# ==================== MENU ENDPOINTS ====================

@router.get("/restaurant/{restaurant_id}", response_model=List[MenuWithCategories])
async def get_restaurant_menus(
    restaurant_id: int,
    active_only: bool = Query(True),
    current_user = Depends(get_current_user_optional)
):
    """Get all menus for a restaurant with categories and dishes (public endpoint)."""
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
    
    menus = await db.menu.find_many(
        where=where_clause,
        include={
            "categories": {
                "where": {"isActive": True} if active_only else {},
                "include": {
                    "dishes": {
                        "where": {"isAvailable": True} if active_only else {},
                        "orderBy": {"displayOrder": "asc"}
                    }
                },
                "orderBy": {"displayOrder": "asc"}
            }
        },
        order={"displayOrder": "asc"}
    )
    
    return [MenuWithCategories.model_validate(menu) for menu in menus]


@router.post("/", response_model=MenuResponse)
async def create_menu(
    menu_data: MenuCreate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Create a new menu (Manager/Admin only)."""
    db = get_db()
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": menu_data.restaurantId})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != menu_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create menus for your own restaurant"
        )
    
    try:
        menu = await db.menu.create(
            data={
                "restaurantId": menu_data.restaurantId,
                "name": menu_data.name,
                "description": menu_data.description,
                "isActive": menu_data.isActive,
                "displayOrder": menu_data.displayOrder
            }
        )
        
        return MenuResponse.model_validate(menu)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating menu: {str(e)}"
        )


@router.put("/{menu_id}", response_model=MenuResponse)
async def update_menu(
    menu_id: int,
    menu_data: MenuUpdate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Update menu (Manager/Admin only)."""
    db = get_db()
    
    # Check if menu exists
    menu = await db.menu.find_unique(
        where={"id": menu_id},
        include={"restaurant": True}
    )
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update menus for your own restaurant"
        )
    
    # Prepare update data
    update_data = {}
    for field, value in menu_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    try:
        updated_menu = await db.menu.update(
            where={"id": menu_id},
            data=update_data
        )
        
        return MenuResponse.model_validate(updated_menu)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating menu: {str(e)}"
        )


@router.delete("/{menu_id}")
async def delete_menu(
    menu_id: int,
    current_user = Depends(get_current_manager_or_admin)
):
    """Delete menu (Manager/Admin only)."""
    db = get_db()
    
    # Check if menu exists
    menu = await db.menu.find_unique(
        where={"id": menu_id},
        include={"restaurant": True}
    )
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete menus for your own restaurant"
        )
    
    try:
        await db.menu.delete(where={"id": menu_id})
        return {"message": f"Menu '{menu.name}' deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting menu: {str(e)}"
        )


# ==================== MENU CATEGORY ENDPOINTS ====================

@router.post("/categories", response_model=MenuCategoryResponse)
async def create_menu_category(
    category_data: MenuCategoryCreate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Create a new menu category (Manager/Admin only)."""
    db = get_db()
    
    # Check if menu exists and get restaurant info
    menu = await db.menu.find_unique(
        where={"id": category_data.menuId},
        include={"restaurant": True}
    )
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create categories for your own restaurant's menus"
        )
    
    try:
        category = await db.menucategory.create(
            data={
                "menuId": category_data.menuId,
                "name": category_data.name,
                "description": category_data.description,
                "image": category_data.image,
                "isActive": category_data.isActive,
                "displayOrder": category_data.displayOrder
            }
        )
        
        return MenuCategoryResponse.model_validate(category)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating menu category: {str(e)}"
        )


@router.put("/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_menu_category(
    category_id: int,
    category_data: MenuCategoryUpdate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Update menu category (Manager/Admin only)."""
    db = get_db()
    
    # Check if category exists
    category = await db.menucategory.find_unique(
        where={"id": category_id},
        include={"menu": {"include": {"restaurant": True}}}
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu category not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update categories for your own restaurant's menus"
        )
    
    # Prepare update data
    update_data = {}
    for field, value in category_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    try:
        updated_category = await db.menucategory.update(
            where={"id": category_id},
            data=update_data
        )
        
        return MenuCategoryResponse.model_validate(updated_category)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating menu category: {str(e)}"
        )


@router.delete("/categories/{category_id}")
async def delete_menu_category(
    category_id: int,
    current_user = Depends(get_current_manager_or_admin)
):
    """Delete menu category (Manager/Admin only)."""
    db = get_db()
    
    # Check if category exists
    category = await db.menucategory.find_unique(
        where={"id": category_id},
        include={"menu": {"include": {"restaurant": True}}}
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu category not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete categories for your own restaurant's menus"
        )
    
    try:
        await db.menucategory.delete(where={"id": category_id})
        return {"message": f"Category '{category.name}' deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting menu category: {str(e)}"
        )


# ==================== DISH ENDPOINTS ====================

@router.post("/dishes", response_model=DishResponse)
async def create_dish(
    dish_data: DishCreate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Create a new dish (Manager/Admin only)."""
    db = get_db()
    
    # Check if category exists and get restaurant info
    category = await db.menucategory.find_unique(
        where={"id": dish_data.categoryId},
        include={"menu": {"include": {"restaurant": True}}}
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu category not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create dishes for your own restaurant's menus"
        )
    
    try:
        dish = await db.dish.create(
            data={
                "categoryId": dish_data.categoryId,
                "name": dish_data.name,
                "description": dish_data.description,
                "price": dish_data.price,
                "image": dish_data.image,
                "gallery": dish_data.gallery or [],
                "isAvailable": dish_data.isAvailable,
                "quantity": dish_data.quantity,
                "preparationTime": dish_data.preparationTime,
                "popularity": dish_data.popularity,
                "displayOrder": dish_data.displayOrder
            }
        )
        
        return DishResponse.model_validate(dish)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating dish: {str(e)}"
        )


@router.get("/dishes/{dish_id}", response_model=DishResponse)
async def get_dish(
    dish_id: int,
    current_user = Depends(get_current_user_optional)
):
    """Get dish by ID (public endpoint)."""
    db = get_db()
    
    dish = await db.dish.find_unique(where={"id": dish_id})
    
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    return DishResponse.model_validate(dish)


@router.put("/dishes/{dish_id}", response_model=DishResponse)
async def update_dish(
    dish_id: int,
    dish_data: DishUpdate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Update dish (Manager/Admin only)."""
    db = get_db()
    
    # Check if dish exists
    dish = await db.dish.find_unique(
        where={"id": dish_id},
        include={"category": {"include": {"menu": {"include": {"restaurant": True}}}}}
    )
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update dishes for your own restaurant's menus"
        )
    
    # Prepare update data
    update_data = {}
    for field, value in dish_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    try:
        updated_dish = await db.dish.update(
            where={"id": dish_id},
            data=update_data
        )
        
        return DishResponse.model_validate(updated_dish)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating dish: {str(e)}"
        )


@router.delete("/dishes/{dish_id}")
async def delete_dish(
    dish_id: int,
    current_user = Depends(get_current_manager_or_admin)
):
    """Delete dish (Manager/Admin only)."""
    db = get_db()
    
    # Check if dish exists
    dish = await db.dish.find_unique(
        where={"id": dish_id},
        include={"category": {"include": {"menu": {"include": {"restaurant": True}}}}}
    )
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete dishes for your own restaurant's menus"
        )
    
    try:
        await db.dish.delete(where={"id": dish_id})
        return {"message": f"Dish '{dish.name}' deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting dish: {str(e)}"
        )


@router.patch("/dishes/{dish_id}/toggle-availability")
async def toggle_dish_availability(
    dish_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Toggle dish availability (Staff only - for their restaurant)."""
    db = get_db()
    
    # Check if dish exists
    dish = await db.dish.find_unique(
        where={"id": dish_id},
        include={"category": {"include": {"menu": {"include": {"restaurant": True}}}}}
    )
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage dishes for your own restaurant"
        )
    
    try:
        updated_dish = await db.dish.update(
            where={"id": dish_id},
            data={"isAvailable": not dish.isAvailable}
        )
        
        return {
            "message": f"Dish '{dish.name}' {'made available' if updated_dish.isAvailable else 'made unavailable'}",
            "dish": DishResponse.model_validate(updated_dish)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating dish availability: {str(e)}"
        )


@router.patch("/dishes/{dish_id}/update-quantity")
async def update_dish_quantity(
    dish_id: int,
    quantity: int = Query(..., ge=0),
    current_user = Depends(get_current_staff_user)
):
    """Update dish quantity (Staff only - for their restaurant)."""
    db = get_db()
    
    # Check if dish exists
    dish = await db.dish.find_unique(
        where={"id": dish_id},
        include={"category": {"include": {"menu": {"include": {"restaurant": True}}}}}
    )
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage dishes for your own restaurant"
        )
    
    try:
        updated_dish = await db.dish.update(
            where={"id": dish_id},
            data={
                "quantity": quantity,
                "isAvailable": quantity > 0  # Auto-disable if quantity is 0
            }
        )
        
        return {
            "message": f"Dish '{dish.name}' quantity updated to {quantity}",
            "dish": DishResponse.model_validate(updated_dish)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating dish quantity: {str(e)}"
        )
