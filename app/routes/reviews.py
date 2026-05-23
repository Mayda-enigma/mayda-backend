from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.middleware.roles import get_current_staff_user, get_current_user
from app.models.review import (
    DishReviewsResponse,
    RestaurantReviewsResponse,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewStats,
    ReviewUpdate,
)
from app.models.sqlalchemy_models import (
    Dish,
    Menu,
    MenuCategory,
    Order,
    OrderItem,
    OrderStatus,
    Restaurant,
    Review,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


# ==================== PUBLIC REVIEW ENDPOINTS ====================


@router.get("/restaurant/{restaurant_id}", response_model=RestaurantReviewsResponse)
async def get_restaurant_reviews(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating_filter: int | None = Query(None, ge=1, le=5),
    verified_only: bool = Query(False),
    db: AsyncSession = Depends(get_db_session),
):
    """Get reviews for a restaurant (Public endpoint)."""

    restaurant = await db.get(Restaurant, restaurant_id)

    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive",
        )

    where_clause = [Review.restaurantId == restaurant_id]
    if rating_filter:
        where_clause.append(Review.rating == rating_filter)
    if verified_only:
        where_clause.append(Review.isVerified == True)

    reviews = (
        (
            await db.execute(
                select(Review)
                .where(and_(*where_clause))
                .options(selectinload(Review.user), selectinload(Review.dish))
                .offset(skip)
                .limit(limit)
                .order_by(Review.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )

    all_reviews = (await db.execute(select(Review).where(Review.restaurantId == restaurant_id))).scalars().all()

    total_reviews = len(all_reviews)
    if total_reviews > 0:
        average_rating = sum(review.rating for review in all_reviews) / total_reviews

        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in all_reviews:
            rating_distribution[review.rating] += 1

        verified_reviews = len([r for r in all_reviews if r.isVerified])
    else:
        average_rating = 0
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        verified_reviews = 0

    review_list = []
    for review in reviews:
        review_dict = review.__dict__.copy()
        review_dict["customerName"] = f"{review.user.firstName} {review.user.lastName}" if review.user else "Anonymous"
        review_dict["restaurantName"] = restaurant.name
        review_dict["dishName"] = review.dish.name if review.dish else None
        review_list.append(ReviewListResponse.model_validate(review_dict))

    latest_reviews = review_list[:5]

    stats = ReviewStats(
        totalReviews=total_reviews,
        averageRating=round(average_rating, 2),
        ratingDistribution=rating_distribution,
        verifiedReviews=verified_reviews,
        latestReviews=latest_reviews,
    )

    return RestaurantReviewsResponse(restaurant=restaurant.__dict__, stats=stats, reviews=review_list)


@router.get("/dish/{dish_id}", response_model=DishReviewsResponse)
async def get_dish_reviews(
    dish_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating_filter: int | None = Query(None, ge=1, le=5),
    verified_only: bool = Query(False),
    db: AsyncSession = Depends(get_db_session),
):
    """Get reviews for a specific dish (Public endpoint)."""

    dish = (
        await db.execute(
            select(Dish)
            .where(Dish.id == dish_id)
            .options(selectinload(Dish.category).selectinload(MenuCategory.menu).selectinload(Menu.restaurant))
        )
    ).scalar_one_or_none()

    if not dish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dish not found")

    where_clause = [Review.dishId == dish_id]
    if rating_filter:
        where_clause.append(Review.rating == rating_filter)
    if verified_only:
        where_clause.append(Review.isVerified == True)

    reviews = (
        (
            await db.execute(
                select(Review)
                .where(and_(*where_clause))
                .options(selectinload(Review.user))
                .offset(skip)
                .limit(limit)
                .order_by(Review.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )

    all_reviews = (await db.execute(select(Review).where(Review.dishId == dish_id))).scalars().all()

    total_reviews = len(all_reviews)
    if total_reviews > 0:
        average_rating = sum(review.rating for review in all_reviews) / total_reviews

        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in all_reviews:
            rating_distribution[review.rating] += 1

        verified_reviews = len([r for r in all_reviews if r.isVerified])
    else:
        average_rating = 0
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        verified_reviews = 0

    review_list = []
    for review in reviews:
        review_dict = review.__dict__.copy()
        review_dict["customerName"] = f"{review.user.firstName} {review.user.lastName}" if review.user else "Anonymous"
        review_dict["restaurantName"] = dish.category.menu.restaurant.name
        review_dict["dishName"] = dish.name
        review_list.append(ReviewListResponse.model_validate(review_dict))

    latest_reviews = review_list[:5]

    stats = ReviewStats(
        totalReviews=total_reviews,
        averageRating=round(average_rating, 2),
        ratingDistribution=rating_distribution,
        verifiedReviews=verified_reviews,
        latestReviews=latest_reviews,
    )

    return DishReviewsResponse(
        dish={"id": dish.id, "name": dish.name, "price": dish.price},
        restaurant=dish.category.menu.restaurant.__dict__,
        stats=stats,
        reviews=review_list,
    )


# ==================== AUTHENTICATED REVIEW ENDPOINTS ====================


@router.post("/", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create review for authenticated user."""

    restaurant = await db.get(Restaurant, review_data.restaurantId)
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive",
        )

    if review_data.dishId:
        dish = (
            await db.execute(
                select(Dish)
                .where(Dish.id == review_data.dishId)
                .options(selectinload(Dish.category).selectinload(MenuCategory.menu))
            )
        ).scalar_one_or_none()
        if not dish:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dish not found")

        if dish.category.menu.restaurantId != review_data.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dish does not belong to the specified restaurant",
            )

    existing_where = [
        Review.userId == current_user.id,
        Review.restaurantId == review_data.restaurantId,
    ]
    if review_data.dishId:
        existing_where.append(Review.dishId == review_data.dishId)
    else:
        existing_where.append(Review.dishId == None)

    existing_review = (await db.execute(select(Review).where(and_(*existing_where)))).scalar_one_or_none()

    if existing_review:
        detail = "You have already reviewed this "
        detail += "dish" if review_data.dishId else "restaurant"
        detail += ". You can update your existing review instead."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    has_ordered = (
        await db.execute(
            select(Order).where(
                and_(
                    Order.userId == current_user.id,
                    Order.restaurantId == review_data.restaurantId,
                    Order.status == OrderStatus.COMPLETED,
                )
            )
        )
    ).scalar_one_or_none()

    is_verified = False
    if has_ordered:
        if review_data.dishId:
            ordered_dish = (
                await db.execute(
                    select(OrderItem).where(
                        and_(
                            OrderItem.dishId == review_data.dishId,
                            OrderItem.order.has(
                                and_(
                                    Order.userId == current_user.id,
                                    Order.restaurantId == review_data.restaurantId,
                                    Order.status == OrderStatus.COMPLETED,
                                )
                            ),
                        )
                    )
                )
            ).scalar_one_or_none()
            is_verified = bool(ordered_dish)
        else:
            is_verified = True

    sentiment = None
    sentiment_score = None
    if review_data.comment:
        comment_lower = review_data.comment.lower()
        positive_words = [
            "good",
            "great",
            "excellent",
            "amazing",
            "love",
            "delicious",
            "fantastic",
            "wonderful",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "hate",
            "disgusting",
            "horrible",
            "worst",
        ]

        positive_count = sum(1 for word in positive_words if word in comment_lower)
        negative_count = sum(1 for word in negative_words if word in comment_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            sentiment_score = min(0.8, 0.5 + (positive_count * 0.1))
        elif negative_count > positive_count:
            sentiment = "negative"
            sentiment_score = max(0.2, 0.5 - (negative_count * 0.1))
        else:
            sentiment = "neutral"
            sentiment_score = 0.5

    try:
        review = Review(
            userId=current_user.id,
            restaurantId=review_data.restaurantId,
            dishId=review_data.dishId,
            rating=review_data.rating,
            comment=review_data.comment,
            sentiment=sentiment,
            sentimentScore=sentiment_score,
            isVerified=is_verified,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)

        complete_review = (
            await db.execute(
                select(Review)
                .where(Review.id == review.id)
                .options(
                    selectinload(Review.user),
                    selectinload(Review.restaurant),
                    selectinload(Review.dish),
                )
            )
        ).scalar_one_or_none()

        return ReviewResponse.model_validate(complete_review)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating review: {str(e)}",
        )


@router.get("/my-reviews", response_model=list[ReviewListResponse])
async def get_my_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get current user's reviews."""

    reviews = (
        (
            await db.execute(
                select(Review)
                .where(Review.userId == current_user.id)
                .options(selectinload(Review.restaurant), selectinload(Review.dish))
                .offset(skip)
                .limit(limit)
                .order_by(Review.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )

    review_list = []
    for review in reviews:
        review_dict = review.__dict__.copy()
        review_dict["customerName"] = f"{current_user.firstName} {current_user.lastName}"
        review_dict["restaurantName"] = review.restaurant.name
        review_dict["dishName"] = review.dish.name if review.dish else None
        review_list.append(ReviewListResponse.model_validate(review_dict))

    return review_list


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get review by ID. Users can only see their own reviews, staff can see restaurant reviews."""

    review = (
        await db.execute(
            select(Review)
            .where(Review.id == review_id)
            .options(
                selectinload(Review.user),
                selectinload(Review.restaurant),
                selectinload(Review.dish),
            )
        )
    ).scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if current_user.role == "ADMIN":
        pass
    elif current_user.role in ["WAITER", "CHEF", "MANAGER"]:
        if current_user.restaurantId != review.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view reviews for your restaurant",
            )
    else:
        if review.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own reviews",
            )

    return ReviewResponse.model_validate(review)


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    review_update: ReviewUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update review (Customer only - their own reviews)."""

    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if review.userId != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own reviews",
        )

    update_data = {}
    if review_update.rating is not None:
        update_data["rating"] = review_update.rating

    if review_update.comment is not None:
        update_data["comment"] = review_update.comment

        comment_lower = review_update.comment.lower()
        positive_words = [
            "good",
            "great",
            "excellent",
            "amazing",
            "love",
            "delicious",
            "fantastic",
            "wonderful",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "hate",
            "disgusting",
            "horrible",
            "worst",
        ]

        positive_count = sum(1 for word in positive_words if word in comment_lower)
        negative_count = sum(1 for word in negative_words if word in comment_lower)

        if positive_count > negative_count:
            update_data["sentiment"] = "positive"
            update_data["sentimentScore"] = min(0.8, 0.5 + (positive_count * 0.1))
        elif negative_count > positive_count:
            update_data["sentiment"] = "negative"
            update_data["sentimentScore"] = max(0.2, 0.5 - (negative_count * 0.1))
        else:
            update_data["sentiment"] = "neutral"
            update_data["sentimentScore"] = 0.5

    if update_data:
        update_data["updatedAt"] = datetime.now()
        for key, value in update_data.items():
            setattr(review, key, value)
        await db.commit()
        await db.refresh(review)

    result = (
        await db.execute(
            select(Review)
            .where(Review.id == review_id)
            .options(
                selectinload(Review.user),
                selectinload(Review.restaurant),
                selectinload(Review.dish),
            )
        )
    ).scalar_one_or_none()

    return ReviewResponse.model_validate(result)


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete review (Customer or Staff)."""

    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if current_user.role == "ADMIN":
        pass
    elif current_user.role in ["MANAGER"]:
        if current_user.restaurantId != review.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete reviews for your restaurant",
            )
    else:
        if review.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own reviews",
            )

    try:
        await db.delete(review)
        await db.commit()
        return {"message": "Review deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting review: {str(e)}",
        )


# ==================== STAFF REVIEW MANAGEMENT ====================


@router.get("/restaurant/{restaurant_id}/management", response_model=list[ReviewListResponse])
async def get_restaurant_reviews_management(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    rating_filter: int | None = Query(None, ge=1, le=5),
    sentiment_filter: str | None = Query(None),
    current_user=Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get restaurant reviews for management (Staff only)."""

    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view reviews for your own restaurant",
        )

    where_clause = [Review.restaurantId == restaurant_id]
    if rating_filter:
        where_clause.append(Review.rating == rating_filter)
    if sentiment_filter:
        where_clause.append(Review.sentiment == sentiment_filter)

    reviews = (
        (
            await db.execute(
                select(Review)
                .where(and_(*where_clause))
                .options(
                    selectinload(Review.user),
                    selectinload(Review.restaurant),
                    selectinload(Review.dish),
                )
                .offset(skip)
                .limit(limit)
                .order_by(Review.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )

    review_list = []
    for review in reviews:
        review_dict = review.__dict__.copy()
        review_dict["customerName"] = f"{review.user.firstName} {review.user.lastName}" if review.user else "Anonymous"
        review_dict["restaurantName"] = review.restaurant.name
        review_dict["dishName"] = review.dish.name if review.dish else None
        review_list.append(ReviewListResponse.model_validate(review_dict))

    return review_list
