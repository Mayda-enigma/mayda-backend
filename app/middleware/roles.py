from fastapi import HTTPException, status, Depends
from functools import wraps
from typing import List, Callable, Any
from app.middleware.auth import auth_middleware, security
from app.models.user import UserRole


class RoleMiddleware:
    """Middleware for role-based access control."""
    
    @staticmethod
    def require_roles(allowed_roles: List[UserRole]):
        """Decorator to require specific roles for endpoint access."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Get current user from the dependency injection
                current_user = None
                for arg in args:
                    if hasattr(arg, 'role'):
                        current_user = arg
                        break
                
                if not current_user:
                    # Try to get from kwargs
                    current_user = kwargs.get('current_user')
                
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                if current_user.role not in allowed_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def require_staff():
        """Decorator to require staff roles (WAITER, CHEF, MANAGER, ADMIN)."""
        return RoleMiddleware.require_roles([
            UserRole.WAITER, 
            UserRole.CHEF, 
            UserRole.MANAGER, 
            UserRole.ADMIN
        ])
    
    @staticmethod
    def require_manager_or_admin():
        """Decorator to require manager or admin roles."""
        return RoleMiddleware.require_roles([UserRole.MANAGER, UserRole.ADMIN])
    
    @staticmethod
    def require_admin():
        """Decorator to require admin role only."""
        return RoleMiddleware.require_roles([UserRole.ADMIN])
    
    @staticmethod
    def require_restaurant_staff(restaurant_id: int):
        """Decorator to require staff roles and verify restaurant association."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Get current user
                current_user = None
                for arg in args:
                    if hasattr(arg, 'role'):
                        current_user = arg
                        break
                
                if not current_user:
                    current_user = kwargs.get('current_user')
                
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # Check if user is staff
                staff_roles = [UserRole.WAITER, UserRole.CHEF, UserRole.MANAGER, UserRole.ADMIN]
                if current_user.role not in staff_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Staff access required"
                    )
                
                # Admin can access any restaurant
                if current_user.role == UserRole.ADMIN:
                    return await func(*args, **kwargs)
                
                # Other staff must be associated with the restaurant
                if current_user.restaurantId != restaurant_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. You are not associated with this restaurant"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


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


# Instance of role middleware
role_middleware = RoleMiddleware()
