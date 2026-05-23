from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.middleware.roles import get_current_staff_user, get_current_user
from app.models.loyalty import (
    LoyaltyCardResponse,
    LoyaltyProgramInfo,
    LoyaltyStatsResponse,
    LoyaltyTransactionCreate,
    LoyaltyTransactionListResponse,
    LoyaltyTransactionResponse,
    PointsEarnedRequest,
    PointsEarnedResponse,
    PointsRedemptionRequest,
    PointsRedemptionResponse,
    RestaurantLoyaltyStatsResponse,
)
from app.models.sqlalchemy_models import (
    LoyaltyCard,
    LoyaltyTransaction,
    Order,
    Restaurant,
)

router = APIRouter(prefix="/loyalty", tags=["Loyalty Cards & Points"])

_LOYALTY_PROGRAM_INFO = LoyaltyProgramInfo(pointsPerDollar=1.0, pointsToMoneyRatio=100, minimumRedemption=100)


# ==================== LOYALTY PROGRAM INFO ====================


@router.get("/program-info", response_model=LoyaltyProgramInfo)
async def get_loyalty_program_info():
    """Get loyalty program information (Public endpoint)."""
    return _LOYALTY_PROGRAM_INFO


# ==================== USER LOYALTY ENDPOINTS ====================


@router.get("/my-card", response_model=LoyaltyCardResponse)
async def get_my_loyalty_card(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    """Get current user's loyalty card."""

    result = await db.execute(
        select(LoyaltyCard).where(LoyaltyCard.userId == current_user.id).options(selectinload(LoyaltyCard.user))
    )
    loyalty_card = result.scalar_one_or_none()

    if not loyalty_card:
        card = LoyaltyCard(userId=current_user.id, points=0)
        db.add(card)
        await db.commit()
        await db.refresh(card)
        result = await db.execute(
            select(LoyaltyCard).where(LoyaltyCard.id == card.id).options(selectinload(LoyaltyCard.user))
        )
        loyalty_card = result.scalar_one()

    resp = LoyaltyCardResponse.model_validate(loyalty_card)
    if loyalty_card.user:
        resp.user = {
            "firstName": loyalty_card.user.firstName,
            "lastName": loyalty_card.user.lastName,
            "email": loyalty_card.user.email,
        }
    return resp


@router.get("/my-transactions", response_model=list[LoyaltyTransactionListResponse])
async def get_my_loyalty_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    restaurant_id: int | None = Query(None),
    transaction_type: str | None = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get current user's loyalty transactions."""

    result = await db.execute(select(LoyaltyCard).where(LoyaltyCard.userId == current_user.id))
    loyalty_card = result.scalar_one_or_none()

    if not loyalty_card:
        return []

    conditions = [LoyaltyTransaction.loyaltyCardId == loyalty_card.id]
    if restaurant_id:
        conditions.append(LoyaltyTransaction.restaurantId == restaurant_id)
    if transaction_type:
        conditions.append(LoyaltyTransaction.type == transaction_type)

    result = await db.execute(
        select(LoyaltyTransaction)
        .where(and_(*conditions))
        .options(
            selectinload(LoyaltyTransaction.restaurant),
            selectinload(LoyaltyTransaction.loyaltyCard).selectinload(LoyaltyCard.user),
        )
        .offset(skip)
        .limit(limit)
        .order_by(LoyaltyTransaction.createdAt.desc())
    )
    transactions = result.scalars().all()

    transaction_list = []
    for transaction in transactions:
        t = LoyaltyTransactionListResponse.model_validate(transaction)
        t.restaurantName = transaction.restaurant.name
        if transaction.orderId:
            order = await db.get(Order, transaction.orderId)
            if order:
                t.orderNumber = order.orderNumber
        transaction_list.append(t)

    return transaction_list


@router.get("/my-stats", response_model=LoyaltyStatsResponse)
async def get_my_loyalty_stats(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    """Get current user's loyalty statistics."""

    result = await db.execute(select(LoyaltyCard).where(LoyaltyCard.userId == current_user.id))
    loyalty_card = result.scalar_one_or_none()

    if not loyalty_card:
        card = LoyaltyCard(userId=current_user.id, points=0)
        db.add(card)
        await db.commit()
        await db.refresh(card)
        loyalty_card = card

    result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.loyaltyCardId == loyalty_card.id)
        .options(selectinload(LoyaltyTransaction.restaurant))
    )
    all_transactions = result.scalars().all()

    points_earned = sum(t.points for t in all_transactions if t.points > 0)
    points_redeemed = abs(sum(t.points for t in all_transactions if t.points < 0))

    restaurant_points = {}
    for transaction in all_transactions:
        if transaction.points > 0:
            restaurant_name = transaction.restaurant.name
            restaurant_points[restaurant_name] = restaurant_points.get(restaurant_name, 0) + transaction.points

    favorite_restaurants = [
        {"name": name, "pointsEarned": points}
        for name, points in sorted(restaurant_points.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.loyaltyCardId == loyalty_card.id)
        .options(selectinload(LoyaltyTransaction.restaurant))
        .limit(10)
        .order_by(LoyaltyTransaction.createdAt.desc())
    )
    recent_transactions = result.scalars().all()

    recent_list = []
    for transaction in recent_transactions:
        t = LoyaltyTransactionListResponse.model_validate(transaction)
        t.restaurantName = transaction.restaurant.name
        recent_list.append(t)

    return LoyaltyStatsResponse(
        totalPoints=loyalty_card.points,
        pointsEarned=points_earned,
        pointsRedeemed=points_redeemed,
        transactionCount=len(all_transactions),
        favoriteRestaurants=favorite_restaurants,
        recentTransactions=recent_list,
    )


@router.post("/redeem-points", response_model=PointsRedemptionResponse)
async def redeem_points(
    redemption_request: PointsRedemptionRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Redeem loyalty points for discount."""

    result = await db.execute(select(LoyaltyCard).where(LoyaltyCard.userId == current_user.id))
    loyalty_card = result.scalar_one_or_none()

    if not loyalty_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty card not found. Make a purchase first to create your loyalty account.",
        )

    if loyalty_card.points < redemption_request.pointsToRedeem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient points. You have {loyalty_card.points} points, need {redemption_request.pointsToRedeem}.",  # noqa: E501
        )

    if redemption_request.pointsToRedeem < _LOYALTY_PROGRAM_INFO.minimumRedemption:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum redemption is {_LOYALTY_PROGRAM_INFO.minimumRedemption} points.",
        )

    restaurant = await db.get(Restaurant, redemption_request.restaurantId)
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive",
        )

    discount_amount = redemption_request.pointsToRedeem / _LOYALTY_PROGRAM_INFO.pointsToMoneyRatio

    try:
        transaction = LoyaltyTransaction(
            loyaltyCardId=loyalty_card.id,
            restaurantId=redemption_request.restaurantId,
            points=-redemption_request.pointsToRedeem,
            type="REDEEMED",
            description=redemption_request.description,
        )
        db.add(transaction)

        loyalty_card.points -= redemption_request.pointsToRedeem

        await db.commit()
        await db.refresh(loyalty_card)

        return PointsRedemptionResponse(
            success=True,
            pointsRedeemed=redemption_request.pointsToRedeem,
            discountAmount=discount_amount,
            remainingPoints=loyalty_card.points,
            message=f"Successfully redeemed {redemption_request.pointsToRedeem} points for ${discount_amount:.2f} discount",  # noqa: E501
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing point redemption: {str(e)}",
        )


# ==================== STAFF LOYALTY MANAGEMENT ====================


@router.post("/award-points", response_model=PointsEarnedResponse)
async def award_points_for_order(
    points_request: PointsEarnedRequest,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Award points to customer for completed order (Staff only)."""

    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to award points",
        )

    result = await db.execute(select(Order).where(Order.id == points_request.orderId).options(selectinload(Order.user)))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if not order.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot award points to orders without registered users",
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != order.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only award points for orders from your restaurant",
        )

    if order.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points can only be awarded for completed orders",
        )

    result = await db.execute(
        select(LoyaltyTransaction).where(
            and_(
                LoyaltyTransaction.orderId == points_request.orderId,
                LoyaltyTransaction.type == "EARNED",
            )
        )
    )
    existing_transaction = result.scalar_one_or_none()

    if existing_transaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points have already been awarded for this order",
        )

    result = await db.execute(select(LoyaltyCard).where(LoyaltyCard.userId == order.user.id))
    loyalty_card = result.scalar_one_or_none()

    if not loyalty_card:
        loyalty_card = LoyaltyCard(userId=order.user.id, points=0)
        db.add(loyalty_card)
        await db.commit()
        await db.refresh(loyalty_card)

    points_earned = int(points_request.orderAmount * _LOYALTY_PROGRAM_INFO.pointsPerDollar)

    try:
        transaction = LoyaltyTransaction(
            loyaltyCardId=loyalty_card.id,
            restaurantId=points_request.restaurantId,
            points=points_earned,
            type="EARNED",
            description=f"Points earned from order #{order.orderNumber}",
            orderId=points_request.orderId,
        )
        db.add(transaction)

        loyalty_card.points += points_earned

        await db.commit()
        await db.refresh(loyalty_card)

        return PointsEarnedResponse(
            pointsEarned=points_earned,
            totalPoints=loyalty_card.points,
            message=f"Awarded {points_earned} points for order #{order.orderNumber}",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error awarding points: {str(e)}",
        )


@router.get("/restaurant/{restaurant_id}/stats", response_model=RestaurantLoyaltyStatsResponse)
async def get_restaurant_loyalty_stats(
    restaurant_id: int,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get loyalty statistics for a restaurant (Staff only)."""

    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view loyalty stats for your own restaurant",
        )

    restaurant = await db.get(Restaurant, restaurant_id)

    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.restaurantId == restaurant_id)
        .options(selectinload(LoyaltyTransaction.loyaltyCard).selectinload(LoyaltyCard.user))
    )
    all_transactions = result.scalars().all()

    total_customers = len(set(t.loyaltyCard.userId for t in all_transactions))
    total_points_given = sum(t.points for t in all_transactions if t.points > 0)
    total_points_redeemed = abs(sum(t.points for t in all_transactions if t.points < 0))

    average_points = total_points_given / total_customers if total_customers > 0 else 0

    customer_points = {}
    for transaction in all_transactions:
        if transaction.points > 0:
            user_id = transaction.loyaltyCard.userId
            user_name = f"{transaction.loyaltyCard.user.firstName} {transaction.loyaltyCard.user.lastName}"
            if user_id not in customer_points:
                customer_points[user_id] = {"name": user_name, "points": 0}
            customer_points[user_id]["points"] += transaction.points

    top_customers = sorted(customer_points.values(), key=lambda x: x["points"], reverse=True)[:10]

    result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.restaurantId == restaurant_id)
        .options(selectinload(LoyaltyTransaction.loyaltyCard).selectinload(LoyaltyCard.user))
        .limit(20)
        .order_by(LoyaltyTransaction.createdAt.desc())
    )
    recent_transactions = result.scalars().all()

    recent_list = []
    for transaction in recent_transactions:
        t = LoyaltyTransactionListResponse.model_validate(transaction)
        t.restaurantName = restaurant.name
        recent_list.append(t)

    return RestaurantLoyaltyStatsResponse(
        restaurantId=restaurant_id,
        restaurantName=restaurant.name,
        totalCustomers=total_customers,
        totalPointsGiven=total_points_given,
        totalPointsRedeemed=total_points_redeemed,
        averagePointsPerCustomer=round(average_points, 2),
        topCustomers=top_customers,
        recentTransactions=recent_list,
    )


@router.post("/manual-transaction", response_model=LoyaltyTransactionResponse)
async def create_manual_loyalty_transaction(
    transaction_data: LoyaltyTransactionCreate,
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create manual loyalty transaction (Manager/Admin only)."""

    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create manual loyalty transactions",
        )

    if current_user.role != "ADMIN" and current_user.restaurantId != transaction_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create transactions for your own restaurant",
        )

    loyalty_card = await db.get(LoyaltyCard, transaction_data.loyaltyCardId)

    if not loyalty_card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loyalty card not found")

    if transaction_data.type == "REDEEMED" and loyalty_card.points < abs(transaction_data.points):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient points. User has {loyalty_card.points} points.",
        )

    try:
        transaction = LoyaltyTransaction(
            loyaltyCardId=transaction_data.loyaltyCardId,
            restaurantId=transaction_data.restaurantId,
            points=transaction_data.points,
            type=transaction_data.type,
            description=transaction_data.description,
            orderId=transaction_data.orderId,
        )
        db.add(transaction)

        loyalty_card.points += transaction_data.points

        await db.commit()
        await db.refresh(transaction)

        result = await db.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.id == transaction.id)
            .options(
                selectinload(LoyaltyTransaction.loyaltyCard).selectinload(LoyaltyCard.user),
                selectinload(LoyaltyTransaction.restaurant),
            )
        )
        complete_transaction = result.scalar_one_or_none()

        resp = LoyaltyTransactionResponse.model_validate(complete_transaction)
        if complete_transaction.loyaltyCard and complete_transaction.loyaltyCard.user:
            resp.loyaltyCard = {
                "user": {
                    "firstName": complete_transaction.loyaltyCard.user.firstName,
                    "lastName": complete_transaction.loyaltyCard.user.lastName,
                }
            }
        if complete_transaction.restaurant:
            resp.restaurant = {"name": complete_transaction.restaurant.name}
        return resp

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating loyalty transaction: {str(e)}",
        )
