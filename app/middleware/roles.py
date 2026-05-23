from fastapi import HTTPException, status, Depends
from app.middleware.auth import auth_middleware, security
from app.models.user import UserRole


# Dependency functions for FastAPI
async def get_current_user(credentials = Depends(security)):
    """FastAPI dependency to get current authenticated user."""
    return await auth_middleware.get_current_user(credentials)


async def get_current_user_optional(credentials = Depends(security)):
    """FastAPI dependency to get current user (optional)."""
    return await auth_middleware.get_current_user_optional(credentials)


async def get_current_staff_user(current_user = Depends(get_current_user)):
    """FastAPI dependency to get current staff user."""
    staff_roles = [UserRole.WAITER, UserRole.CHEF, UserRole.MANAGER, UserRole.ADMIN]
    if current_user.role not in staff_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )
    return current_user


async def get_current_manager_or_admin(current_user = Depends(get_current_user)):
    """FastAPI dependency to get current manager or admin user."""
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required"
        )
    return current_user


async def get_current_admin_user(current_user = Depends(get_current_user)):
    """FastAPI dependency to get current admin user."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_restaurant_staff(
    restaurant_id: int,
    current_user = Depends(get_current_manager_or_admin),
):
    """Ensure manager/admin access is scoped to a permitted restaurant."""
    user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if user_role != UserRole.ADMIN.value and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage staff for your own restaurant"
        )
    return current_user
