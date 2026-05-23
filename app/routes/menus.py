from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List
from app.models.menu import (
    MenuCreate, MenuUpdate, MenuResponse,
    MenuCategoryCreate, MenuCategoryUpdate, MenuCategoryResponse,
    DishCreate, DishUpdate, DishResponse, MenuWithCategories
)
from app.core.database import get_db_session
from app.middleware.roles import (
    get_current_manager_or_admin, get_current_staff_user,
    get_current_user_optional
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from app.models.sqlalchemy_models import Menu, MenuCategory, Dish, Restaurant


router = APIRouter(prefix="/menus", tags=["Menus & Dishes"])


# ==================== MENU ENDPOINTS ====================

@router.get("/restaurant/{restaurant_id}", response_model=List[MenuWithCategories])
async def get_restaurant_menus(
    restaurant_id: int,
    active_only: bool = Query(True),
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get all menus for a restaurant with categories and dishes (public endpoint)."""

    restaurant = await db.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    stmt = select(Menu).where(Menu.restaurantId == restaurant_id)
    if active_only:
        stmt = stmt.where(Menu.isActive == True)
    stmt = stmt.options(
        selectinload(Menu.categories).selectinload(MenuCategory.dishes)
    ).order_by(Menu.displayOrder)

    menus = (await db.execute(stmt)).scalars().all()

    if active_only:
        for menu in menus:
            menu.categories = [c for c in menu.categories if c.isActive]
            for cat in menu.categories:
                cat.dishes = [d for d in cat.dishes if d.isAvailable]

    return [MenuWithCategories.model_validate(menu) for menu in menus]


@router.post("/", response_model=MenuResponse)
async def create_menu(
    menu_data: MenuCreate,
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new menu (Manager/Admin only)."""

    restaurant = await db.get(Restaurant, menu_data.restaurantId)
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != menu_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create menus for your own restaurant"
        )

    try:
        menu = Menu(
            restaurantId=menu_data.restaurantId,
            name=menu_data.name,
            description=menu_data.description,
            isActive=menu_data.isActive,
            displayOrder=menu_data.displayOrder
        )
        db.add(menu)
        await db.commit()
        await db.refresh(menu)

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
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Update menu (Manager/Admin only)."""

    stmt = select(Menu).where(Menu.id == menu_id).options(selectinload(Menu.restaurant))
    menu = (await db.execute(stmt)).scalar_one_or_none()
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update menus for your own restaurant"
        )

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
        for field, value in update_data.items():
            setattr(menu, field, value)
        await db.commit()
        await db.refresh(menu)

        return MenuResponse.model_validate(menu)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating menu: {str(e)}"
        )


@router.delete("/{menu_id}")
async def delete_menu(
    menu_id: int,
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete menu (Manager/Admin only)."""

    stmt = select(Menu).where(Menu.id == menu_id).options(selectinload(Menu.restaurant))
    menu = (await db.execute(stmt)).scalar_one_or_none()
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete menus for your own restaurant"
        )

    try:
        await db.delete(menu)
        await db.commit()
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
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new menu category (Manager/Admin only)."""

    stmt = select(Menu).where(Menu.id == category_data.menuId).options(selectinload(Menu.restaurant))
    menu = (await db.execute(stmt)).scalar_one_or_none()
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create categories for your own restaurant's menus"
        )

    try:
        category = MenuCategory(
            menuId=category_data.menuId,
            name=category_data.name,
            description=category_data.description,
            image=category_data.image,
            isActive=category_data.isActive,
            displayOrder=category_data.displayOrder
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)

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
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Update menu category (Manager/Admin only)."""

    stmt = (
        select(MenuCategory)
        .where(MenuCategory.id == category_id)
        .options(selectinload(MenuCategory.menu).selectinload(Menu.restaurant))
    )
    category = (await db.execute(stmt)).scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu category not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update categories for your own restaurant's menus"
        )

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
        for field, value in update_data.items():
            setattr(category, field, value)
        await db.commit()
        await db.refresh(category)

        return MenuCategoryResponse.model_validate(category)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating menu category: {str(e)}"
        )


@router.delete("/categories/{category_id}")
async def delete_menu_category(
    category_id: int,
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete menu category (Manager/Admin only)."""

    stmt = (
        select(MenuCategory)
        .where(MenuCategory.id == category_id)
        .options(selectinload(MenuCategory.menu).selectinload(Menu.restaurant))
    )
    category = (await db.execute(stmt)).scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu category not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete categories for your own restaurant's menus"
        )

    try:
        await db.delete(category)
        await db.commit()
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
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new dish (Manager/Admin only)."""

    stmt = (
        select(MenuCategory)
        .where(MenuCategory.id == dish_data.categoryId)
        .options(selectinload(MenuCategory.menu).selectinload(Menu.restaurant))
    )
    category = (await db.execute(stmt)).scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu category not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create dishes for your own restaurant's menus"
        )

    try:
        dish = Dish(
            categoryId=dish_data.categoryId,
            name=dish_data.name,
            description=dish_data.description,
            price=dish_data.price,
            image=dish_data.image,
            gallery=dish_data.gallery or [],
            isAvailable=dish_data.isAvailable,
            quantity=dish_data.quantity,
            preparationTime=dish_data.preparationTime,
            popularity=dish_data.popularity,
            displayOrder=dish_data.displayOrder
        )
        db.add(dish)
        await db.commit()
        await db.refresh(dish)

        return DishResponse.model_validate(dish)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating dish: {str(e)}"
        )


@router.get("/dishes/{dish_id}", response_model=DishResponse)
async def get_dish(
    dish_id: int,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """Get dish by ID (public endpoint)."""

    dish = await db.get(Dish, dish_id)

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
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Update dish (Manager/Admin only)."""

    stmt = (
        select(Dish)
        .where(Dish.id == dish_id)
        .options(
            selectinload(Dish.category)
            .selectinload(MenuCategory.menu)
            .selectinload(Menu.restaurant)
        )
    )
    dish = (await db.execute(stmt)).scalar_one_or_none()
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update dishes for your own restaurant's menus"
        )

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
        for field, value in update_data.items():
            setattr(dish, field, value)
        await db.commit()
        await db.refresh(dish)

        return DishResponse.model_validate(dish)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating dish: {str(e)}"
        )


@router.delete("/dishes/{dish_id}")
async def delete_dish(
    dish_id: int,
    current_user = Depends(get_current_manager_or_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete dish (Manager/Admin only)."""

    stmt = (
        select(Dish)
        .where(Dish.id == dish_id)
        .options(
            selectinload(Dish.category)
            .selectinload(MenuCategory.menu)
            .selectinload(Menu.restaurant)
        )
    )
    dish = (await db.execute(stmt)).scalar_one_or_none()
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete dishes for your own restaurant's menus"
        )

    try:
        await db.delete(dish)
        await db.commit()
        return {"message": f"Dish '{dish.name}' deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting dish: {str(e)}"
        )


@router.patch("/dishes/{dish_id}/toggle-availability")
async def toggle_dish_availability(
    dish_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Toggle dish availability (Staff only - for their restaurant)."""

    stmt = (
        select(Dish)
        .where(Dish.id == dish_id)
        .options(
            selectinload(Dish.category)
            .selectinload(MenuCategory.menu)
            .selectinload(Menu.restaurant)
        )
    )
    dish = (await db.execute(stmt)).scalar_one_or_none()
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage dishes for your own restaurant"
        )

    try:
        dish.isAvailable = not dish.isAvailable
        await db.commit()
        await db.refresh(dish)

        return {
            "message": f"Dish '{dish.name}' {'made available' if dish.isAvailable else 'made unavailable'}",
            "dish": DishResponse.model_validate(dish)
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
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update dish quantity (Staff only - for their restaurant)."""

    stmt = (
        select(Dish)
        .where(Dish.id == dish_id)
        .options(
            selectinload(Dish.category)
            .selectinload(MenuCategory.menu)
            .selectinload(Menu.restaurant)
        )
    )
    dish = (await db.execute(stmt)).scalar_one_or_none()
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != dish.category.menu.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage dishes for your own restaurant"
        )

    try:
        dish.quantity = quantity
        dish.isAvailable = quantity > 0
        await db.commit()
        await db.refresh(dish)

        return {
            "message": f"Dish '{dish.name}' quantity updated to {quantity}",
            "dish": DishResponse.model_validate(dish)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating dish quantity: {str(e)}"
        )
