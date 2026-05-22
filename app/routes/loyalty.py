from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.loyalty import (
    LoyaltyCardResponse, LoyaltyTransactionCreate, LoyaltyTransactionResponse,
    LoyaltyTransactionListResponse, PointsRedemptionRequest, PointsRedemptionResponse,
    PointsEarnedRequest, PointsEarnedResponse, LoyaltyStatsResponse,
    RestaurantLoyaltyStatsResponse, LoyaltyProgramInfo
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_staff_user, get_current_user
)


router = APIRouter(prefix="/loyalty", tags=["Loyalty Cards & Points"])


# ==================== LOYALTY PROGRAM INFO ====================

@router.get("/program-info", response_model=LoyaltyProgramInfo)
async def get_loyalty_program_info():
    """Get loyalty program information (Public endpoint)."""
    
    return LoyaltyProgramInfo(
        pointsPerDollar=1.0,  # 1 point per $1 spent
        pointsToMoneyRatio=100,  # 100 points = $1
        minimumRedemption=100  # Minimum 100 points to redeem
    )


# ==================== USER LOYALTY ENDPOINTS ====================

@router.get("/my-card", response_model=LoyaltyCardResponse)
async def get_my_loyalty_card(current_user = Depends(get_current_user)):
    """Get current user's loyalty card."""
    db = get_db()
    
    loyalty_card = await db.loyaltycard.find_unique(
        where={"userId": current_user.id},
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                    "email": True
                }
            }
        }
    )
    
    if not loyalty_card:
        # Create loyalty card if it doesn't exist
        loyalty_card = await db.loyaltycard.create(
            data={
                "userId": current_user.id,
                "points": 0
            },
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True,
                        "email": True
                    }
                }
            }
        )
    
    return LoyaltyCardResponse.model_validate(loyalty_card)


@router.get("/my-transactions", response_model=List[LoyaltyTransactionListResponse])
async def get_my_loyalty_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    restaurant_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """Get current user's loyalty transactions."""
    db = get_db()
    
    # Get user's loyalty card
    loyalty_card = await db.loyaltycard.find_unique(
        where={"userId": current_user.id}
    )
    
    if not loyalty_card:
        return []
    
    # Build where clause
    where_clause = {"loyaltyCardId": loyalty_card.id}
    
    if restaurant_id:
        where_clause["restaurantId"] = restaurant_id
    
    if transaction_type:
        where_clause["type"] = transaction_type
    
    transactions = await db.loyaltytransaction.find_many(
        where=where_clause,
        include={
            "restaurant": {
                "select": {
                    "name": True
                }
            },
            "loyaltyCard": {
                "include": {
                    "user": {
                        "select": {
                            "firstName": True,
                            "lastName": True
                        }
                    }
                }
            }
        },
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    # Format response
    transaction_list = []
    for transaction in transactions:
        transaction_dict = transaction.__dict__.copy()
        transaction_dict["restaurantName"] = transaction.restaurant.name
        
        # Try to get order number if orderId exists
        if transaction.orderId:
            try:
                order = await db.order.find_unique(
                    where={"id": transaction.orderId}
                )
                transaction_dict["orderNumber"] = order.orderNumber if order else None
            except:
                transaction_dict["orderNumber"] = None
        
        transaction_list.append(LoyaltyTransactionListResponse.model_validate(transaction_dict))
    
    return transaction_list


@router.get("/my-stats", response_model=LoyaltyStatsResponse)
async def get_my_loyalty_stats(current_user = Depends(get_current_user)):
    """Get current user's loyalty statistics."""
    db = get_db()
    
    # Get user's loyalty card
    loyalty_card = await db.loyaltycard.find_unique(
        where={"userId": current_user.id}
    )
    
    if not loyalty_card:
        # Create loyalty card if it doesn't exist
        loyalty_card = await db.loyaltycard.create(
            data={
                "userId": current_user.id,
                "points": 0
            }
        )
    
    # Get all transactions
    all_transactions = await db.loyaltytransaction.find_many(
        where={"loyaltyCardId": loyalty_card.id},
        include={
            "restaurant": {
                "select": {
                    "name": True
                }
            }
        }
    )
    
    # Calculate stats
    points_earned = sum(t.points for t in all_transactions if t.points > 0)
    points_redeemed = abs(sum(t.points for t in all_transactions if t.points < 0))
    
    # Get favorite restaurants (by points earned)
    restaurant_points = {}
    for transaction in all_transactions:
        if transaction.points > 0:  # Only count earned points
            restaurant_name = transaction.restaurant.name
            restaurant_points[restaurant_name] = restaurant_points.get(restaurant_name, 0) + transaction.points
    
    favorite_restaurants = [
        {"name": name, "pointsEarned": points}
        for name, points in sorted(restaurant_points.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    # Get recent transactions (last 10)
    recent_transactions = await db.loyaltytransaction.find_many(
        where={"loyaltyCardId": loyalty_card.id},
        include={
            "restaurant": {
                "select": {
                    "name": True
                }
            }
        },
        take=10,
        order={"createdAt": "desc"}
    )
    
    recent_list = []
    for transaction in recent_transactions:
        transaction_dict = transaction.__dict__.copy()
        transaction_dict["restaurantName"] = transaction.restaurant.name
        recent_list.append(LoyaltyTransactionListResponse.model_validate(transaction_dict))
    
    return LoyaltyStatsResponse(
        totalPoints=loyalty_card.points,
        pointsEarned=points_earned,
        pointsRedeemed=points_redeemed,
        transactionCount=len(all_transactions),
        favoriteRestaurants=favorite_restaurants,
        recentTransactions=recent_list
    )


@router.post("/redeem-points", response_model=PointsRedemptionResponse)
async def redeem_points(
    redemption_request: PointsRedemptionRequest,
    current_user = Depends(get_current_user)
):
    """Redeem loyalty points for discount."""
    db = get_db()
    
    # Get user's loyalty card
    loyalty_card = await db.loyaltycard.find_unique(
        where={"userId": current_user.id}
    )
    
    if not loyalty_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty card not found. Make a purchase first to create your loyalty account."
        )
    
    # Check if user has enough points
    if loyalty_card.points < redemption_request.pointsToRedeem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient points. You have {loyalty_card.points} points, need {redemption_request.pointsToRedeem}."
        )
    
    # Check minimum redemption amount
    program_info = await get_loyalty_program_info()
    if redemption_request.pointsToRedeem < program_info.minimumRedemption:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum redemption is {program_info.minimumRedemption} points."
        )
    
    # Validate restaurant exists
    restaurant = await db.restaurant.find_unique(
        where={"id": redemption_request.restaurantId}
    )
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Calculate discount amount (100 points = $1)
    discount_amount = redemption_request.pointsToRedeem / program_info.pointsToMoneyRatio
    
    try:
        # Create redemption transaction
        transaction = await db.loyaltytransaction.create(
            data={
                "loyaltyCardId": loyalty_card.id,
                "restaurantId": redemption_request.restaurantId,
                "points": -redemption_request.pointsToRedeem,  # Negative for redemption
                "type": "REDEEMED",
                "description": redemption_request.description
            }
        )
        
        # Update loyalty card points
        updated_card = await db.loyaltycard.update(
            where={"id": loyalty_card.id},
            data={"points": loyalty_card.points - redemption_request.pointsToRedeem}
        )
        
        return PointsRedemptionResponse(
            success=True,
            pointsRedeemed=redemption_request.pointsToRedeem,
            discountAmount=discount_amount,
            remainingPoints=updated_card.points,
            message=f"Successfully redeemed {redemption_request.pointsToRedeem} points for ${discount_amount:.2f} discount"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing point redemption: {str(e)}"
        )


# ==================== STAFF LOYALTY MANAGEMENT ====================

@router.post("/award-points", response_model=PointsEarnedResponse)
async def award_points_for_order(
    points_request: PointsEarnedRequest,
    current_user = Depends(get_current_staff_user)
):
    """Award points to customer for completed order (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to award points"
        )
    
    # Validate order exists and get customer
    order = await db.order.find_unique(
        where={"id": points_request.orderId},
        include={
            "user": True
        }
    )
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if not order.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot award points to orders without registered users"
        )
    
    # Check if order is from the staff member's restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != order.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only award points for orders from your restaurant"
        )
    
    # Check if order is completed
    if order.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points can only be awarded for completed orders"
        )
    
    # Check if points already awarded for this order
    existing_transaction = await db.loyaltytransaction.find_first(
        where={
            "orderId": points_request.orderId,
            "type": "EARNED"
        }
    )
    
    if existing_transaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points have already been awarded for this order"
        )
    
    # Get or create loyalty card for customer
    loyalty_card = await db.loyaltycard.find_unique(
        where={"userId": order.user.id}
    )
    
    if not loyalty_card:
        loyalty_card = await db.loyaltycard.create(
            data={
                "userId": order.user.id,
                "points": 0
            }
        )
    
    # Calculate points earned (1 point per dollar)
    program_info = await get_loyalty_program_info()
    points_earned = int(points_request.orderAmount * program_info.pointsPerDollar)
    
    try:
        # Create points earned transaction
        transaction = await db.loyaltytransaction.create(
            data={
                "loyaltyCardId": loyalty_card.id,
                "restaurantId": points_request.restaurantId,
                "points": points_earned,
                "type": "EARNED",
                "description": f"Points earned from order #{order.orderNumber}",
                "orderId": points_request.orderId
            }
        )
        
        # Update loyalty card points
        updated_card = await db.loyaltycard.update(
            where={"id": loyalty_card.id},
            data={"points": loyalty_card.points + points_earned}
        )
        
        return PointsEarnedResponse(
            pointsEarned=points_earned,
            totalPoints=updated_card.points,
            message=f"Awarded {points_earned} points for order #{order.orderNumber}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error awarding points: {str(e)}"
        )


@router.get("/restaurant/{restaurant_id}/stats", response_model=RestaurantLoyaltyStatsResponse)
async def get_restaurant_loyalty_stats(
    restaurant_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Get loyalty statistics for a restaurant (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view loyalty stats for your own restaurant"
        )
    
    # Get restaurant
    restaurant = await db.restaurant.find_unique(
        where={"id": restaurant_id}
    )
    
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Get all transactions for this restaurant
    all_transactions = await db.loyaltytransaction.find_many(
        where={"restaurantId": restaurant_id},
        include={
            "loyaltyCard": {
                "include": {
                    "user": {
                        "select": {
                            "firstName": True,
                            "lastName": True
                        }
                    }
                }
            }
        }
    )
    
    # Calculate stats
    total_customers = len(set(t.loyaltyCard.userId for t in all_transactions))
    total_points_given = sum(t.points for t in all_transactions if t.points > 0)
    total_points_redeemed = abs(sum(t.points for t in all_transactions if t.points < 0))
    
    average_points = total_points_given / total_customers if total_customers > 0 else 0
    
    # Get top customers by points earned
    customer_points = {}
    for transaction in all_transactions:
        if transaction.points > 0:  # Only earned points
            user_id = transaction.loyaltyCard.userId
            user_name = f"{transaction.loyaltyCard.user.firstName} {transaction.loyaltyCard.user.lastName}"
            if user_id not in customer_points:
                customer_points[user_id] = {"name": user_name, "points": 0}
            customer_points[user_id]["points"] += transaction.points
    
    top_customers = sorted(customer_points.values(), key=lambda x: x["points"], reverse=True)[:10]
    
    # Get recent transactions
    recent_transactions = await db.loyaltytransaction.find_many(
        where={"restaurantId": restaurant_id},
        include={
            "loyaltyCard": {
                "include": {
                    "user": {
                        "select": {
                            "firstName": True,
                            "lastName": True
                        }
                    }
                }
            }
        },
        take=20,
        order={"createdAt": "desc"}
    )
    
    recent_list = []
    for transaction in recent_transactions:
        transaction_dict = transaction.__dict__.copy()
        transaction_dict["restaurantName"] = restaurant.name
        recent_list.append(LoyaltyTransactionListResponse.model_validate(transaction_dict))
    
    return RestaurantLoyaltyStatsResponse(
        restaurantId=restaurant_id,
        restaurantName=restaurant.name,
        totalCustomers=total_customers,
        totalPointsGiven=total_points_given,
        totalPointsRedeemed=total_points_redeemed,
        averagePointsPerCustomer=round(average_points, 2),
        topCustomers=top_customers,
        recentTransactions=recent_list
    )


@router.post("/manual-transaction", response_model=LoyaltyTransactionResponse)
async def create_manual_loyalty_transaction(
    transaction_data: LoyaltyTransactionCreate,
    current_user = Depends(get_current_staff_user)
):
    """Create manual loyalty transaction (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create manual loyalty transactions"
        )
    
    # Check if user can modify this restaurant's loyalty transactions
    if current_user.role != "ADMIN" and current_user.restaurantId != transaction_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create transactions for your own restaurant"
        )
    
    # Validate loyalty card exists
    loyalty_card = await db.loyaltycard.find_unique(
        where={"id": transaction_data.loyaltyCardId}
    )
    
    if not loyalty_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty card not found"
        )
    
    # For redemptions, check if user has enough points
    if transaction_data.type == "REDEEMED" and loyalty_card.points < abs(transaction_data.points):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient points. User has {loyalty_card.points} points."
        )
    
    try:
        # Create transaction
        transaction = await db.loyaltytransaction.create(
            data={
                "loyaltyCardId": transaction_data.loyaltyCardId,
                "restaurantId": transaction_data.restaurantId,
                "points": transaction_data.points,
                "type": transaction_data.type,
                "description": transaction_data.description,
                "orderId": transaction_data.orderId
            }
        )
        
        # Update loyalty card points
        await db.loyaltycard.update(
            where={"id": transaction_data.loyaltyCardId},
            data={"points": loyalty_card.points + transaction_data.points}
        )
        
        # Fetch complete transaction
        complete_transaction = await db.loyaltytransaction.find_unique(
            where={"id": transaction.id},
            include={
                "loyaltyCard": {
                    "include": {
                        "user": {
                            "select": {
                                "firstName": True,
                                "lastName": True
                            }
                        }
                    }
                },
                "restaurant": {
                    "select": {
                        "name": True
                    }
                }
            }
        )
        
        return LoyaltyTransactionResponse.model_validate(complete_transaction)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating loyalty transaction: {str(e)}"
        )
