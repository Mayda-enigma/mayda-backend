from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.review import (
    ReviewCreate, ReviewUpdate, ReviewResponse, ReviewListResponse,
    ReviewStats, RestaurantReviewsResponse, DishReviewsResponse
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_staff_user, get_current_user
)


router = APIRouter(prefix="/reviews", tags=["Reviews"])


# ==================== PUBLIC REVIEW ENDPOINTS ====================

@router.get("/restaurant/{restaurant_id}", response_model=RestaurantReviewsResponse)
async def get_restaurant_reviews(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    verified_only: bool = Query(False)
):
    """Get reviews for a restaurant (Public endpoint)."""
    db = get_db()
    
    # Validate restaurant exists
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
    if rating_filter:
        where_clause["rating"] = rating_filter
    if verified_only:
        where_clause["isVerified"] = True
    
    # Get reviews with relations
    reviews = await db.review.find_many(
        where=where_clause,
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True
                }
            },
            "dish": {
                "select": {
                    "name": True
                }
            }
        },
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    # Calculate stats
    all_reviews = await db.review.find_many(
        where={"restaurantId": restaurant_id}
    )
    
    total_reviews = len(all_reviews)
    if total_reviews > 0:
        average_rating = sum(review.rating for review in all_reviews) / total_reviews
        
        # Rating distribution
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in all_reviews:
            rating_distribution[review.rating] += 1
        
        verified_reviews = len([r for r in all_reviews if r.isVerified])
    else:
        average_rating = 0
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        verified_reviews = 0
    
    # Format review list
    review_list = []
    for review in reviews:
        review_dict = review.__dict__.copy()
        review_dict["customerName"] = f"{review.user.firstName} {review.user.lastName}" if review.user else "Anonymous"
        review_dict["restaurantName"] = restaurant.name
        review_dict["dishName"] = review.dish.name if review.dish else None
        review_list.append(ReviewListResponse.model_validate(review_dict))
    
    # Latest reviews for stats (top 5)
    latest_reviews = review_list[:5]
    
    stats = ReviewStats(
        totalReviews=total_reviews,
        averageRating=round(average_rating, 2),
        ratingDistribution=rating_distribution,
        verifiedReviews=verified_reviews,
        latestReviews=latest_reviews
    )
    
    return RestaurantReviewsResponse(
        restaurant=restaurant.__dict__,
        stats=stats,
        reviews=review_list
    )


@router.get("/dish/{dish_id}", response_model=DishReviewsResponse)
async def get_dish_reviews(
    dish_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    verified_only: bool = Query(False)
):
    """Get reviews for a specific dish (Public endpoint)."""
    db = get_db()
    
    # Validate dish exists
    dish = await db.dish.find_unique(
        where={"id": dish_id},
        include={
            "category": {
                "include": {
                    "menu": {
                        "include": {
                            "restaurant": {
                                "select": {
                                    "id": True,
                                    "name": True
                                }
                            }
                        }
                    }
                }
            }
        }
    )
    
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Build where clause
    where_clause = {"dishId": dish_id}
    if rating_filter:
        where_clause["rating"] = rating_filter
    if verified_only:
        where_clause["isVerified"] = True
    
    # Get reviews
    reviews = await db.review.find_many(
        where=where_clause,
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True
                }
            }
        },
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    # Calculate stats
    all_reviews = await db.review.find_many(
        where={"dishId": dish_id}
    )
    
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
    
    # Format review list
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
        latestReviews=latest_reviews
    )
    
    return DishReviewsResponse(
        dish={"id": dish.id, "name": dish.name, "price": dish.price},
        restaurant=dish.category.menu.restaurant.__dict__,
        stats=stats,
        reviews=review_list
    )


# ==================== AUTHENTICATED REVIEW ENDPOINTS ====================

@router.post("/", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    current_user = Depends(get_current_user)
):
    """Create review for authenticated user."""
    db = get_db()
    
    # Validate restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": review_data.restaurantId})
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Validate dish if provided
    if review_data.dishId:
        dish = await db.dish.find_unique(
            where={"id": review_data.dishId},
            include={
                "category": {
                    "include": {
                        "menu": True
                    }
                }
            }
        )
        if not dish:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dish not found"
            )
        
        # Ensure dish belongs to the restaurant
        if dish.category.menu.restaurantId != review_data.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dish does not belong to the specified restaurant"
            )
    
    # Check if user already reviewed this restaurant/dish
    existing_review = await db.review.find_first(
        where={
            "userId": current_user.id,
            "restaurantId": review_data.restaurantId,
            "dishId": review_data.dishId
        }
    )
    
    if existing_review:
        detail = "You have already reviewed this "
        detail += "dish" if review_data.dishId else "restaurant"
        detail += ". You can update your existing review instead."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    
    # Check if user has actually ordered from this restaurant (for verification)
    has_ordered = await db.order.find_first(
        where={
            "userId": current_user.id,
            "restaurantId": review_data.restaurantId,
            "status": {"in": ["COMPLETED"]}
        }
    )
    
    # If reviewing a specific dish, check if they ordered that dish
    is_verified = False
    if has_ordered:
        if review_data.dishId:
            # Check if they ordered this specific dish
            ordered_dish = await db.orderitem.find_first(
                where={
                    "dishId": review_data.dishId,
                    "order": {
                        "userId": current_user.id,
                        "restaurantId": review_data.restaurantId,
                        "status": "COMPLETED"
                    }
                }
            )
            is_verified = bool(ordered_dish)
        else:
            # Restaurant review - just need to have ordered from restaurant
            is_verified = True
    
    # Simple sentiment analysis (basic implementation)
    sentiment = None
    sentiment_score = None
    if review_data.comment:
        comment_lower = review_data.comment.lower()
        positive_words = ["good", "great", "excellent", "amazing", "love", "delicious", "fantastic", "wonderful"]
        negative_words = ["bad", "terrible", "awful", "hate", "disgusting", "horrible", "worst"]
        
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
        review = await db.review.create(
            data={
                "userId": current_user.id,
                "restaurantId": review_data.restaurantId,
                "dishId": review_data.dishId,
                "rating": review_data.rating,
                "comment": review_data.comment,
                "sentiment": sentiment,
                "sentimentScore": sentiment_score,
                "isVerified": is_verified
            }
        )
        
        # Fetch complete review with relations
        complete_review = await db.review.find_unique(
            where={"id": review.id},
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True
                    }
                },
                "restaurant": {
                    "select": {
                        "name": True
                    }
                },
                "dish": {
                    "select": {
                        "name": True,
                        "price": True
                    }
                }
            }
        )
        
        return ReviewResponse.model_validate(complete_review)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating review: {str(e)}"
        )


@router.get("/my-reviews", response_model=List[ReviewListResponse])
async def get_my_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_user)
):
    """Get current user's reviews."""
    db = get_db()
    
    reviews = await db.review.find_many(
        where={"userId": current_user.id},
        include={
            "restaurant": {
                "select": {
                    "name": True
                }
            },
            "dish": {
                "select": {
                    "name": True
                }
            }
        },
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    # Format response
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
    current_user = Depends(get_current_user)
):
    """Get review by ID. Users can only see their own reviews, staff can see restaurant reviews."""
    db = get_db()
    
    review = await db.review.find_unique(
        where={"id": review_id},
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True
                }
            },
            "restaurant": {
                "select": {
                    "name": True
                }
            },
            "dish": {
                "select": {
                    "name": True,
                    "price": True
                }
            }
        }
    )
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    # Check permissions
    if current_user.role == "ADMIN":
        # Admin can see all reviews
        pass
    elif current_user.role in ["WAITER", "CHEF", "MANAGER"]:
        # Staff can see reviews for their restaurant
        if current_user.restaurantId != review.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view reviews for your restaurant"
            )
    else:
        # Regular users can only see their own reviews
        if review.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own reviews"
            )
    
    return ReviewResponse.model_validate(review)


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    review_update: ReviewUpdate,
    current_user = Depends(get_current_user)
):
    """Update review (Customer only - their own reviews)."""
    db = get_db()
    
    # Check if review exists
    review = await db.review.find_unique(where={"id": review_id})
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    # Only the review author can update it
    if review.userId != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own reviews"
        )
    
    # Prepare update data
    update_data = {}
    if review_update.rating is not None:
        update_data["rating"] = review_update.rating
    
    if review_update.comment is not None:
        update_data["comment"] = review_update.comment
        
        # Re-analyze sentiment if comment is updated
        comment_lower = review_update.comment.lower()
        positive_words = ["good", "great", "excellent", "amazing", "love", "delicious", "fantastic", "wonderful"]
        negative_words = ["bad", "terrible", "awful", "hate", "disgusting", "horrible", "worst"]
        
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
    
    try:
        updated_review = await db.review.update(
            where={"id": review_id},
            data=update_data,
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True
                    }
                },
                "restaurant": {
                    "select": {
                        "name": True
                    }
                },
                "dish": {
                    "select": {
                        "name": True,
                        "price": True
                    }
                }
            }
        )
        
        return ReviewResponse.model_validate(updated_review)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating review: {str(e)}"
        )


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    current_user = Depends(get_current_user)
):
    """Delete review (Customer or Staff)."""
    db = get_db()
    
    # Check if review exists
    review = await db.review.find_unique(where={"id": review_id})
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    # Check permissions
    if current_user.role == "ADMIN":
        # Admin can delete any review
        pass
    elif current_user.role in ["MANAGER"]:
        # Managers can delete reviews for their restaurant
        if current_user.restaurantId != review.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete reviews for your restaurant"
            )
    else:
        # Regular users can only delete their own reviews
        if review.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own reviews"
            )
    
    try:
        await db.review.delete(where={"id": review_id})
        return {"message": "Review deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting review: {str(e)}"
        )


# ==================== STAFF REVIEW MANAGEMENT ====================

@router.get("/restaurant/{restaurant_id}/management", response_model=List[ReviewListResponse])
async def get_restaurant_reviews_management(
    restaurant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    sentiment_filter: Optional[str] = Query(None),
    current_user = Depends(get_current_staff_user)
):
    """Get restaurant reviews for management (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view reviews for your own restaurant"
        )
    
    # Build where clause
    where_clause = {"restaurantId": restaurant_id}
    if rating_filter:
        where_clause["rating"] = rating_filter
    if sentiment_filter:
        where_clause["sentiment"] = sentiment_filter
    
    reviews = await db.review.find_many(
        where=where_clause,
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                    "phone": True,
                    "email": True
                }
            },
            "restaurant": {
                "select": {
                    "name": True
                }
            },
            "dish": {
                "select": {
                    "name": True
                }
            }
        },
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    # Format response with more customer details for staff
    review_list = []
    for review in reviews:
        review_dict = review.__dict__.copy()
        review_dict["customerName"] = f"{review.user.firstName} {review.user.lastName}" if review.user else "Anonymous"
        review_dict["restaurantName"] = review.restaurant.name
        review_dict["dishName"] = review.dish.name if review.dish else None
        review_list.append(ReviewListResponse.model_validate(review_dict))
    
    return review_list
