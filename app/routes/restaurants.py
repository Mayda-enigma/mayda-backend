from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.models.restaurant import (
    RestaurantCreate, RestaurantUpdate, RestaurantResponse, 
    RestaurantListResponse
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_admin_user, get_current_manager_or_admin,
    get_current_user_optional
)


router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.get("/", response_model=List[RestaurantListResponse])
async def get_restaurants(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active_only: bool = Query(True),
    current_user = Depends(get_current_user_optional)
):
    """Get list of restaurants (public endpoint)."""
    db = get_db()
    
    where_clause = {}
    if active_only:
        where_clause["isActive"] = True
    
    restaurants = await db.restaurant.find_many(
        where=where_clause,
        include={"address": True},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    return [RestaurantListResponse.model_validate(restaurant) for restaurant in restaurants]


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(
    restaurant_id: int,
    current_user = Depends(get_current_user_optional)
):
    """Get restaurant by ID (public endpoint)."""
    db = get_db()
    
    restaurant = await db.restaurant.find_unique(
        where={"id": restaurant_id},
        include={"address": True}
    )
    
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    return RestaurantResponse.model_validate(restaurant)


@router.post("/", response_model=RestaurantResponse)
async def create_restaurant(
    restaurant_data: RestaurantCreate,
    current_user = Depends(get_current_admin_user)
):
    """Create a new restaurant (Admin only)."""
    db = get_db()
    
    try:
        # Create restaurant with address in a transaction
        result = await db.transaction([
            # Create restaurant
            db.restaurant.create(
                data={
                    "name": restaurant_data.name,
                    "description": restaurant_data.description,
                    "phone": restaurant_data.phone,
                    "email": restaurant_data.email,
                    "website": restaurant_data.website,
                    "operatingHours": restaurant_data.operatingHours,
                    "logo": restaurant_data.logo,
                    "coverImage": restaurant_data.coverImage,
                    "gallery": restaurant_data.gallery or [],
                    "isActive": restaurant_data.isActive
                }
            )
        ])
        
        restaurant = result[0]
        
        # Create address for the restaurant
        await db.address.create(
            data={
                "restaurantId": restaurant.id,
                "street": restaurant_data.street,
                "city": restaurant_data.city,
                "latitude": restaurant_data.latitude,
                "longitude": restaurant_data.longitude,
                "isDefault": True
            }
        )
        
        # Fetch restaurant with address
        restaurant_with_address = await db.restaurant.find_unique(
            where={"id": restaurant.id},
            include={"address": True}
        )
        
        return RestaurantResponse.model_validate(restaurant_with_address)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating restaurant: {str(e)}"
        )


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
async def update_restaurant(
    restaurant_id: int,
    restaurant_data: RestaurantUpdate,
    current_user = Depends(get_current_manager_or_admin)
):
    """Update restaurant (Manager/Admin only). Managers can only update their own restaurant."""
    db = get_db()
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions - managers can only update their own restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own restaurant"
        )
    
    # Prepare update data
    update_data = {}
    for field, value in restaurant_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    try:
        updated_restaurant = await db.restaurant.update(
            where={"id": restaurant_id},
            data=update_data,
            include={"address": True}
        )
        
        return RestaurantResponse.model_validate(updated_restaurant)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating restaurant: {str(e)}"
        )


@router.delete("/{restaurant_id}")
async def delete_restaurant(
    restaurant_id: int,
    current_user = Depends(get_current_admin_user)
):
    """Delete restaurant (Admin only)."""
    db = get_db()
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    try:
        await db.restaurant.delete(where={"id": restaurant_id})
        return {"message": "Restaurant deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting restaurant: {str(e)}"
        )


@router.patch("/{restaurant_id}/toggle-status")
async def toggle_restaurant_status(
    restaurant_id: int,
    current_user = Depends(get_current_manager_or_admin)
):
    """Toggle restaurant active status (Manager/Admin only)."""
    db = get_db()
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own restaurant"
        )
    
    try:
        updated_restaurant = await db.restaurant.update(
            where={"id": restaurant_id},
            data={"isActive": not restaurant.isActive},
            include={"address": True}
        )
        
        return {
            "message": f"Restaurant {'activated' if updated_restaurant.isActive else 'deactivated'} successfully",
            "restaurant": RestaurantResponse.model_validate(updated_restaurant)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating restaurant status: {str(e)}"
        )


@router.get("/{restaurant_id}/staff")
async def get_restaurant_staff(
    restaurant_id: int,
    current_user = Depends(get_current_manager_or_admin)
):
    """Get restaurant staff (Manager/Admin only). Managers can only see their own restaurant staff."""
    db = get_db()
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own restaurant staff"
        )
    
    staff = await db.user.find_many(
        where={
            "restaurantId": restaurant_id,
            "role": {"in": ["WAITER", "CHEF", "MANAGER"]}
        },
        order={"role": "asc"}
    )
    
    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.name,
        "staff": staff,
        "total_staff": len(staff)
    }
