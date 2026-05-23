from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.middleware.roles import get_current_staff_user
from app.models.promotion import (
    ActivePromotionsResponse,
    DiscountType,
    PromotionCreate,
    PromotionListResponse,
    PromotionResponse,
    PromotionType,
    PromotionUpdate,
    PromotionUsageRequest,
    PromotionUsageResponse,
)
from app.models.sqlalchemy_models import Dish, Menu, MenuCategory, Promotion, Restaurant

router = APIRouter(prefix="/promotions", tags=["Promotions"])


# ==================== PUBLIC PROMOTION ENDPOINTS ====================


@router.get("/active", response_model=ActivePromotionsResponse)
async def get_active_promotions(
    restaurant_id: int | None = Query(None),
    promotion_type: PromotionType | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """Get all active promotions (Public endpoint)."""

    conditions = [
        Promotion.isActive == True,
        Promotion.startDate <= datetime.now(),
        Promotion.endDate >= datetime.now(),
    ]

    if restaurant_id:
        conditions.append(Promotion.restaurantId == restaurant_id)

    if promotion_type:
        conditions.append(Promotion.type == promotion_type.value)

    stmt = (
        select(Promotion)
        .options(selectinload(Promotion.restaurant), selectinload(Promotion.dishes))
        .where(and_(*conditions))
        .order_by(Promotion.createdAt.desc())
    )

    result = await db.execute(stmt)
    promotions = result.scalars().all()

    # Filter out promotions from inactive restaurants
    active_promotions = [p for p in promotions if p.restaurant.isActive]

    # Separate general restaurant promotions from dish-specific ones
    restaurant_promotions = []
    dish_specific_promotions = []

    for promotion in active_promotions:
        promotion.restaurantName = promotion.restaurant.name
        promotion.isExpired = promotion.endDate < datetime.now()
        promotion.dishCount = len(promotion.dishes)

        promotion_item = PromotionListResponse.model_validate(promotion)

        if promotion.dishes:
            dish_specific_promotions.append(promotion_item)
        else:
            restaurant_promotions.append(promotion_item)

    return ActivePromotionsResponse(
        totalPromotions=len(active_promotions),
        restaurantPromotions=restaurant_promotions,
        dishSpecificPromotions=dish_specific_promotions,
    )


@router.get("/restaurant/{restaurant_id}", response_model=list[PromotionListResponse])
async def get_restaurant_promotions(
    restaurant_id: int,
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """Get promotions for a specific restaurant (Public endpoint)."""

    # Validate restaurant exists and is active
    restaurant = await db.get(Restaurant, restaurant_id)

    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive",
        )

    # Build where clause
    conditions = [Promotion.restaurantId == restaurant_id]

    if active_only:
        current_time = datetime.now()
        conditions.extend(
            [
                Promotion.isActive == True,
                Promotion.startDate <= current_time,
                Promotion.endDate >= current_time,
            ]
        )

    stmt = (
        select(Promotion)
        .options(selectinload(Promotion.dishes))
        .where(and_(*conditions))
        .offset(skip)
        .limit(limit)
        .order_by(Promotion.startDate.desc())
    )

    result = await db.execute(stmt)
    promotions = result.scalars().all()

    # Format response
    promotion_list = []
    for promotion in promotions:
        promotion.restaurantName = restaurant.name
        promotion.isExpired = promotion.endDate < datetime.now()
        promotion.dishCount = len(promotion.dishes)
        promotion_list.append(PromotionListResponse.model_validate(promotion))

    return promotion_list


@router.post("/calculate", response_model=PromotionUsageResponse)
async def calculate_promotion_discount(request: PromotionUsageRequest, db: AsyncSession = Depends(get_db_session)):
    """Calculate discount for a promotion (Public endpoint)."""

    stmt = select(Promotion).options(selectinload(Promotion.restaurant)).where(Promotion.id == request.promotionId)
    result = await db.execute(stmt)
    promotion = result.scalar_one_or_none()

    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    if not promotion.restaurant.isActive:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Restaurant is currently inactive",
        )

    # Check if promotion is active
    current_time = datetime.now()
    if not promotion.isActive:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion is not active",
        )

    if current_time < promotion.startDate:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion has not started yet",
        )

    if current_time > promotion.endDate:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion has expired",
        )

    # Check usage limit
    if promotion.maxUses and promotion.currentUses >= promotion.maxUses:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion usage limit reached",
        )

    # Check minimum order amount
    if promotion.minOrderAmount and request.orderAmount < promotion.minOrderAmount:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message=f"Minimum order amount is {promotion.minOrderAmount}",
        )

    # Calculate discount
    discount_amount = 0

    if promotion.discountType == DiscountType.PERCENTAGE:
        discount_amount = (request.orderAmount * promotion.discountValue) / 100
    elif promotion.discountType == DiscountType.FIXED_AMOUNT:
        discount_amount = min(promotion.discountValue, request.orderAmount)

    final_amount = max(0, request.orderAmount - discount_amount)

    return PromotionUsageResponse(
        applicable=True,
        discountAmount=discount_amount,
        finalAmount=final_amount,
        message=f"Discount applied: {promotion.title}",
    )


# ==================== AUTHENTICATED PROMOTION ENDPOINTS ====================


@router.get("/{promotion_id}", response_model=PromotionResponse)
async def get_promotion(promotion_id: int, db: AsyncSession = Depends(get_db_session)):
    """Get promotion by ID (Public endpoint)."""

    stmt = (
        select(Promotion)
        .options(selectinload(Promotion.restaurant), selectinload(Promotion.dishes))
        .where(Promotion.id == promotion_id)
    )
    result = await db.execute(stmt)
    promotion = result.scalar_one_or_none()

    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    if not promotion.restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant is currently inactive",
        )

    return PromotionResponse.model_validate(promotion)


# ==================== STAFF PROMOTION MANAGEMENT ====================


@router.post("/", response_model=PromotionResponse)
async def create_promotion(
    promotion_data: PromotionCreate,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create promotion (Manager/Admin only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create promotions",
        )

    # Check if user can create promotions for this restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create promotions for your own restaurant",
        )

    # Validate restaurant exists
    restaurant = await db.get(Restaurant, promotion_data.restaurantId)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # Validate dishes if provided
    dish_objects = []
    if promotion_data.dishIds:
        stmt = (
            select(Dish)
            .join(MenuCategory, Dish.categoryId == MenuCategory.id)
            .join(Menu, MenuCategory.menuId == Menu.id)
            .where(
                Dish.id.in_(promotion_data.dishIds),
                Menu.restaurantId == promotion_data.restaurantId,
            )
        )
        result = await db.execute(stmt)
        dish_objects = result.scalars().all()

        if len(dish_objects) != len(promotion_data.dishIds):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some dishes don't exist or don't belong to this restaurant",
            )

    try:
        # Create promotion
        promotion = Promotion(
            restaurantId=promotion_data.restaurantId,
            title=promotion_data.title,
            description=promotion_data.description,
            image=promotion_data.image,
            type=promotion_data.type.value,
            discountType=promotion_data.discountType.value,
            discountValue=promotion_data.discountValue,
            minOrderAmount=promotion_data.minOrderAmount,
            startDate=promotion_data.startDate,
            endDate=promotion_data.endDate,
            maxUses=promotion_data.maxUses,
            currentUses=0,
            isActive=True,
        )

        db.add(promotion)
        await db.commit()
        await db.refresh(promotion)

        # Connect dishes if provided
        if dish_objects:
            promotion.dishes = dish_objects
            await db.commit()

        # Fetch complete promotion
        stmt = (
            select(Promotion)
            .options(selectinload(Promotion.restaurant), selectinload(Promotion.dishes))
            .where(Promotion.id == promotion.id)
        )
        result = await db.execute(stmt)
        complete_promotion = result.scalar_one()

        return PromotionResponse.model_validate(complete_promotion)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating promotion: {str(e)}",
        )


@router.get("/management/restaurant/{restaurant_id}", response_model=list[PromotionListResponse])
async def get_restaurant_promotions_management(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active_only: bool = Query(False),
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get restaurant promotions for management (Staff only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view promotions for your own restaurant",
        )

    # Build where clause
    conditions = [Promotion.restaurantId == restaurant_id]

    if active_only:
        current_time = datetime.now()
        conditions.extend(
            [
                Promotion.isActive == True,
                Promotion.startDate <= current_time,
                Promotion.endDate >= current_time,
            ]
        )

    stmt = (
        select(Promotion)
        .options(selectinload(Promotion.restaurant), selectinload(Promotion.dishes))
        .where(and_(*conditions))
        .offset(skip)
        .limit(limit)
        .order_by(Promotion.createdAt.desc())
    )

    result = await db.execute(stmt)
    promotions = result.scalars().all()

    # Format response
    promotion_list = []
    for promotion in promotions:
        promotion.restaurantName = promotion.restaurant.name
        promotion.isExpired = promotion.endDate < datetime.now()
        promotion.dishCount = len(promotion.dishes)
        promotion_list.append(PromotionListResponse.model_validate(promotion))

    return promotion_list


@router.put("/{promotion_id}", response_model=PromotionResponse)
async def update_promotion(
    promotion_id: int,
    promotion_update: PromotionUpdate,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update promotion (Manager/Admin only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can update promotions",
        )

    # Check if promotion exists
    promotion = await db.get(Promotion, promotion_id)
    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    # Check permissions for restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update promotions for your own restaurant",
        )

    # Map update fields
    if promotion_update.title is not None:
        promotion.title = promotion_update.title

    if promotion_update.description is not None:
        promotion.description = promotion_update.description

    if promotion_update.image is not None:
        promotion.image = promotion_update.image

    if promotion_update.discountValue is not None:
        promotion.discountValue = promotion_update.discountValue

    if promotion_update.minOrderAmount is not None:
        promotion.minOrderAmount = promotion_update.minOrderAmount

    if promotion_update.endDate is not None:
        promotion.endDate = promotion_update.endDate

    if promotion_update.maxUses is not None:
        promotion.maxUses = promotion_update.maxUses

    if promotion_update.isActive is not None:
        promotion.isActive = promotion_update.isActive

    try:
        # Update dish connections if provided
        if promotion_update.dishIds is not None:
            if promotion_update.dishIds:
                # Validate dishes belong to the restaurant
                stmt = (
                    select(Dish)
                    .join(MenuCategory, Dish.categoryId == MenuCategory.id)
                    .join(Menu, MenuCategory.menuId == Menu.id)
                    .where(
                        Dish.id.in_(promotion_update.dishIds),
                        Menu.restaurantId == promotion.restaurantId,
                    )
                )
                result = await db.execute(stmt)
                dishes = result.scalars().all()

                if len(dishes) != len(promotion_update.dishIds):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Some dishes don't exist or don't belong to this restaurant",
                    )

                promotion.dishes = dishes
            else:
                promotion.dishes = []

        await db.commit()
        await db.refresh(promotion)

        # Fetch complete updated promotion
        stmt = (
            select(Promotion)
            .options(selectinload(Promotion.restaurant), selectinload(Promotion.dishes))
            .where(Promotion.id == promotion_id)
        )
        result = await db.execute(stmt)
        complete_promotion = result.scalar_one()

        return PromotionResponse.model_validate(complete_promotion)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating promotion: {str(e)}",
        )


@router.delete("/{promotion_id}")
async def delete_promotion(
    promotion_id: int,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete promotion (Manager/Admin only)."""

    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can delete promotions",
        )

    # Check if promotion exists
    promotion = await db.get(Promotion, promotion_id)
    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    # Check permissions for restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete promotions for your own restaurant",
        )

    try:
        await db.delete(promotion)
        await db.commit()
        return {"message": "Promotion deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting promotion: {str(e)}",
        )


@router.post("/{promotion_id}/increment-usage")
async def increment_promotion_usage(
    promotion_id: int,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Increment promotion usage count (Staff only - when processing orders)."""

    promotion = await db.get(Promotion, promotion_id)
    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify promotions for your own restaurant",
        )

    # Check if promotion has usage limit
    if promotion.maxUses and promotion.currentUses >= promotion.maxUses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promotion usage limit already reached",
        )

    try:
        promotion.currentUses = promotion.currentUses + 1
        await db.commit()
        await db.refresh(promotion)

        return {
            "message": "Promotion usage incremented",
            "currentUses": promotion.currentUses,
            "maxUses": promotion.maxUses,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error incrementing promotion usage: {str(e)}",
        )
