from fastapi import APIRouter, Depends
from app.middleware.roles import (
    get_current_user, get_current_staff_user, 
    get_current_manager_or_admin, get_current_admin_user
)
from app.models.auth import UserResponse


router = APIRouter(prefix="/protected", tags=["Protected Routes"])


@router.get("/profile")
async def get_profile(current_user=Depends(get_current_user)):
    """Get user profile - requires authentication."""
    return {
        "message": "This is a protected route",
        "user": UserResponse.model_validate(current_user)
    }


@router.get("/staff-only")
async def staff_only_route(current_user=Depends(get_current_staff_user)):
    """Staff only route - requires WAITER, CHEF, MANAGER, or ADMIN role."""
    return {
        "message": "This route is accessible only to staff members",
        "user_role": current_user.role,
        "restaurant_id": current_user.restaurantId
    }


@router.get("/manager-only")
async def manager_only_route(current_user=Depends(get_current_manager_or_admin)):
    """Manager or Admin only route."""
    return {
        "message": "This route is accessible only to managers and admins",
        "user_role": current_user.role,
        "restaurant_id": current_user.restaurantId
    }


@router.get("/admin-only")
async def admin_only_route(current_user=Depends(get_current_admin_user)):
    """Admin only route."""
    return {
        "message": "This route is accessible only to admins",
        "user_role": current_user.role
    }


@router.get("/restaurant/{restaurant_id}/staff")
async def get_restaurant_staff(
    restaurant_id: int,
    current_user=Depends(get_current_manager_or_admin)
):
    """Get staff for a specific restaurant - Manager/Admin only."""
    # Additional check for restaurant association (unless admin)
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access staff from your restaurant"
        )
    
    return {
        "message": f"Staff list for restaurant {restaurant_id}",
        "requester_role": current_user.role,
        "restaurant_id": restaurant_id
    }
