from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.auth.jwt import verify_token, get_user_id_from_token
from app.core.database import get_db
from app.models.sqlalchemy_models import User


security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Middleware for JWT authentication."""

    @staticmethod
    async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = None):
        """Get current user from JWT token (optional - returns None if no token)."""
        if not credentials:
            return None

        token = credentials.credentials
        user_id = get_user_id_from_token(token)

        if not user_id:
            return None

        try:
            db = await get_db()
            result = await db.execute(
                select(User)
                .where(User.id == user_id)
                .options(selectinload(User.restaurant), selectinload(User.address))
            )
            user = result.scalar_one_or_none()
            await db.close()
            return user
        except Exception:
            return None

    @staticmethod
    async def get_current_user(credentials: HTTPAuthorizationCredentials):
        """Get current user from JWT token (required - raises exception if invalid)."""
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials
        payload = verify_token(token)

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            db = await get_db()
            result = await db.execute(
                select(User)
                .where(User.id == int(user_id))
                .options(selectinload(User.restaurant), selectinload(User.address))
            )
            user = result.scalar_one_or_none()
            await db.close()

            if user is None or not user.isActive:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return user
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )


auth_middleware = AuthMiddleware()
