from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.promotion import (
    PromotionCreate, PromotionUpdate, PromotionResponse, PromotionListResponse,
    PromotionUsageRequest, PromotionUsageResponse, ActivePromotionsResponse,
    PromotionType, DiscountType
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_staff_user, get_current_user
)


router = APIRouter(prefix="/promotions", tags=["Promotions"])


# ==================== PUBLIC PROMOTION ENDPOINTS ====================

@router.get("/active", response_model=ActivePromotionsResponse)
async def get_active_promotions(
    restaurant_id: Optional[int] = Query(None),
    promotion_type: Optional[PromotionType] = Query(None)
):
    """Get all active promotions (Public endpoint)."""
    db = get_db()
    
    # Build where clause for active promotions
    where_clause = {
        "isActive": True,
        "startDate": {"lte": datetime.now()},
        "endDate": {"gte": datetime.now()}
    }
    
    if restaurant_id:
        where_clause["restaurantId"] = restaurant_id
    
    if promotion_type:
        where_clause["type"] = promotion_type.value
    
    # Get active promotions
    promotions = await db.promotion.find_many(
        where=where_clause,
        include={
            "restaurant": {
                "select": {
                    "name": True,
                    "isActive": True
                }
            },
            "dishes": {
                "select": {
                    "id": True,
                    "name": True,
                    "price": True
                }
            }
        },
        order={"createdAt": "desc"}
    )
    
    # Filter out promotions from inactive restaurants
    active_promotions = [p for p in promotions if p.restaurant.isActive]
    
    # Separate general restaurant promotions from dish-specific ones
    restaurant_promotions = []
    dish_specific_promotions = []
    
    for promotion in active_promotions:
        promotion_dict = promotion.__dict__.copy()
        promotion_dict["restaurantName"] = promotion.restaurant.name
        promotion_dict["isExpired"] = promotion.endDate < datetime.now()
        promotion_dict["dishCount"] = len(promotion.dishes)
        
        promotion_item = PromotionListResponse.model_validate(promotion_dict)
        
        if promotion.dishes:
            dish_specific_promotions.append(promotion_item)
        else:
            restaurant_promotions.append(promotion_item)
    
    return ActivePromotionsResponse(
        totalPromotions=len(active_promotions),
        restaurantPromotions=restaurant_promotions,
        dishSpecificPromotions=dish_specific_promotions
    )


@router.get("/restaurant/{restaurant_id}", response_model=List[PromotionListResponse])
async def get_restaurant_promotions(
    restaurant_id: int,
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Get promotions for a specific restaurant (Public endpoint)."""
    db = get_db()
    
    # Validate restaurant exists and is active
    restaurant = await db.restaurant.find_unique(
        where={"id": restaurant_id}
    )
    
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Build where clause
    where_clause = {"restaurantId": restaurant_id}
    
    if active_only:
        current_time = datetime.now()
        where_clause.update({
            "isActive": True,
            "startDate": {"lte": current_time},
            "endDate": {"gte": current_time}
        })
    
    promotions = await db.promotion.find_many(
        where=where_clause,
        include={
            "dishes": {
                "select": {
                    "id": True,
                    "name": True
                }
            }
        },
        skip=skip,
        take=limit,
        order={"startDate": "desc"}
    )
    
    # Format response
    promotion_list = []
    for promotion in promotions:
        promotion_dict = promotion.__dict__.copy()
        promotion_dict["restaurantName"] = restaurant.name
        promotion_dict["isExpired"] = promotion.endDate < datetime.now()
        promotion_dict["dishCount"] = len(promotion.dishes)
        promotion_list.append(PromotionListResponse.model_validate(promotion_dict))
    
    return promotion_list


@router.post("/calculate", response_model=PromotionUsageResponse)
async def calculate_promotion_discount(request: PromotionUsageRequest):
    """Calculate discount for a promotion (Public endpoint)."""
    db = get_db()
    
    promotion = await db.promotion.find_unique(
        where={"id": request.promotionId},
        include={
            "restaurant": {
                "select": {
                    "isActive": True
                }
            }
        }
    )
    
    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )
    
    if not promotion.restaurant.isActive:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Restaurant is currently inactive"
        )
    
    # Check if promotion is active
    current_time = datetime.now()
    if not promotion.isActive:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion is not active"
        )
    
    if current_time < promotion.startDate:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion has not started yet"
        )
    
    if current_time > promotion.endDate:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion has expired"
        )
    
    # Check usage limit
    if promotion.maxUses and promotion.currentUses >= promotion.maxUses:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message="Promotion usage limit reached"
        )
    
    # Check minimum order amount
    if promotion.minOrderAmount and request.orderAmount < promotion.minOrderAmount:
        return PromotionUsageResponse(
            applicable=False,
            discountAmount=0,
            finalAmount=request.orderAmount,
            message=f"Minimum order amount is {promotion.minOrderAmount}"
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
        message=f"Discount applied: {promotion.title}"
    )


# ==================== AUTHENTICATED PROMOTION ENDPOINTS ====================

@router.get("/{promotion_id}", response_model=PromotionResponse)
async def get_promotion(promotion_id: int):
    """Get promotion by ID (Public endpoint)."""
    db = get_db()
    
    promotion = await db.promotion.find_unique(
        where={"id": promotion_id},
        include={
            "restaurant": {
                "select": {
                    "name": True,
                    "isActive": True
                }
            },
            "dishes": {
                "select": {
                    "id": True,
                    "name": True,
                    "price": True
                }
            }
        }
    )
    
    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )
    
    if not promotion.restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant is currently inactive"
        )
    
    return PromotionResponse.model_validate(promotion)


# ==================== STAFF PROMOTION MANAGEMENT ====================

@router.post("/", response_model=PromotionResponse)
async def create_promotion(
    promotion_data: PromotionCreate,
    current_user = Depends(get_current_staff_user)
):
    """Create promotion (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create promotions"
        )
    
    # Check if user can create promotions for this restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create promotions for your own restaurant"
        )
    
    # Validate restaurant exists
    restaurant = await db.restaurant.find_unique(
        where={"id": promotion_data.restaurantId}
    )
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Validate dishes if provided
    if promotion_data.dishIds:
        dishes = await db.dish.find_many(
            where={
                "id": {"in": promotion_data.dishIds},
                "category": {
                    "menu": {
                        "restaurantId": promotion_data.restaurantId
                    }
                }
            }
        )
        
        if len(dishes) != len(promotion_data.dishIds):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some dishes don't exist or don't belong to this restaurant"
            )
    
    try:
        # Create promotion
        promotion = await db.promotion.create(
            data={
                "restaurantId": promotion_data.restaurantId,
                "title": promotion_data.title,
                "description": promotion_data.description,
                "image": promotion_data.image,
                "type": promotion_data.type.value,
                "discountType": promotion_data.discountType.value,
                "discountValue": promotion_data.discountValue,
                "minOrderAmount": promotion_data.minOrderAmount,
                "startDate": promotion_data.startDate,
                "endDate": promotion_data.endDate,
                "maxUses": promotion_data.maxUses,
                "currentUses": 0,
                "isActive": True
            }
        )
        
        # Connect dishes if provided
        if promotion_data.dishIds:
            await db.promotion.update(
                where={"id": promotion.id},
                data={
                    "dishes": {
                        "connect": [{"id": dish_id} for dish_id in promotion_data.dishIds]
                    }
                }
            )
        
        # Fetch complete promotion
        complete_promotion = await db.promotion.find_unique(
            where={"id": promotion.id},
            include={
                "restaurant": {
                    "select": {
                        "name": True
                    }
                },
                "dishes": {
                    "select": {
                        "id": True,
                        "name": True,
                        "price": True
                    }
                }
            }
        )
        
        return PromotionResponse.model_validate(complete_promotion)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating promotion: {str(e)}"
        )


@router.get("/management/restaurant/{restaurant_id}", response_model=List[PromotionListResponse])
async def get_restaurant_promotions_management(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active_only: bool = Query(False),
    current_user = Depends(get_current_staff_user)
):
    """Get restaurant promotions for management (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view promotions for your own restaurant"
        )
    
    # Build where clause
    where_clause = {"restaurantId": restaurant_id}
    
    if active_only:
        current_time = datetime.now()
        where_clause.update({
            "isActive": True,
            "startDate": {"lte": current_time},
            "endDate": {"gte": current_time}
        })
    
    promotions = await db.promotion.find_many(
        where=where_clause,
        include={
            "restaurant": {
                "select": {
                    "name": True
                }
            },
            "dishes": {
                "select": {
                    "id": True,
                    "name": True
                }
            }
        },
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    # Format response
    promotion_list = []
    for promotion in promotions:
        promotion_dict = promotion.__dict__.copy()
        promotion_dict["restaurantName"] = promotion.restaurant.name
        promotion_dict["isExpired"] = promotion.endDate < datetime.now()
        promotion_dict["dishCount"] = len(promotion.dishes)
        promotion_list.append(PromotionListResponse.model_validate(promotion_dict))
    
    return promotion_list


@router.put("/{promotion_id}", response_model=PromotionResponse)
async def update_promotion(
    promotion_id: int,
    promotion_update: PromotionUpdate,
    current_user = Depends(get_current_staff_user)
):
    """Update promotion (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can update promotions"
        )
    
    # Check if promotion exists
    promotion = await db.promotion.find_unique(where={"id": promotion_id})
    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )
    
    # Check permissions for restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update promotions for your own restaurant"
        )
    
    # Prepare update data
    update_data = {}
    
    if promotion_update.title is not None:
        update_data["title"] = promotion_update.title
    
    if promotion_update.description is not None:
        update_data["description"] = promotion_update.description
    
    if promotion_update.image is not None:
        update_data["image"] = promotion_update.image
    
    if promotion_update.discountValue is not None:
        update_data["discountValue"] = promotion_update.discountValue
    
    if promotion_update.minOrderAmount is not None:
        update_data["minOrderAmount"] = promotion_update.minOrderAmount
    
    if promotion_update.endDate is not None:
        update_data["endDate"] = promotion_update.endDate
    
    if promotion_update.maxUses is not None:
        update_data["maxUses"] = promotion_update.maxUses
    
    if promotion_update.isActive is not None:
        update_data["isActive"] = promotion_update.isActive
    
    if update_data:
        update_data["updatedAt"] = datetime.now()
    
    try:
        # Update promotion
        updated_promotion = await db.promotion.update(
            where={"id": promotion_id},
            data=update_data
        )
        
        # Update dish connections if provided
        if promotion_update.dishIds is not None:
            # Disconnect all current dishes
            await db.promotion.update(
                where={"id": promotion_id},
                data={
                    "dishes": {
                        "set": []
                    }
                }
            )
            
            # Connect new dishes
            if promotion_update.dishIds:
                # Validate dishes belong to the restaurant
                dishes = await db.dish.find_many(
                    where={
                        "id": {"in": promotion_update.dishIds},
                        "category": {
                            "menu": {
                                "restaurantId": promotion.restaurantId
                            }
                        }
                    }
                )
                
                if len(dishes) != len(promotion_update.dishIds):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Some dishes don't exist or don't belong to this restaurant"
                    )
                
                await db.promotion.update(
                    where={"id": promotion_id},
                    data={
                        "dishes": {
                            "connect": [{"id": dish_id} for dish_id in promotion_update.dishIds]
                        }
                    }
                )
        
        # Fetch complete updated promotion
        complete_promotion = await db.promotion.find_unique(
            where={"id": promotion_id},
            include={
                "restaurant": {
                    "select": {
                        "name": True
                    }
                },
                "dishes": {
                    "select": {
                        "id": True,
                        "name": True,
                        "price": True
                    }
                }
            }
        )
        
        return PromotionResponse.model_validate(complete_promotion)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating promotion: {str(e)}"
        )


@router.delete("/{promotion_id}")
async def delete_promotion(
    promotion_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Delete promotion (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can delete promotions"
        )
    
    # Check if promotion exists
    promotion = await db.promotion.find_unique(where={"id": promotion_id})
    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )
    
    # Check permissions for restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete promotions for your own restaurant"
        )
    
    try:
        await db.promotion.delete(where={"id": promotion_id})
        return {"message": "Promotion deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting promotion: {str(e)}"
        )


@router.post("/{promotion_id}/increment-usage")
async def increment_promotion_usage(
    promotion_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Increment promotion usage count (Staff only - when processing orders)."""
    db = get_db()
    
    promotion = await db.promotion.find_unique(where={"id": promotion_id})
    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != promotion.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify promotions for your own restaurant"
        )
    
    # Check if promotion has usage limit
    if promotion.maxUses and promotion.currentUses >= promotion.maxUses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promotion usage limit already reached"
        )
    
    try:
        updated_promotion = await db.promotion.update(
            where={"id": promotion_id},
            data={"currentUses": promotion.currentUses + 1}
        )
        
        return {
            "message": "Promotion usage incremented",
            "currentUses": updated_promotion.currentUses,
            "maxUses": updated_promotion.maxUses
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error incrementing promotion usage: {str(e)}"
        )
