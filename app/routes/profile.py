from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.middleware.roles import get_current_user_optional
from app.models.sqlalchemy_models import User

router = APIRouter(prefix="/profile", tags=["Profile"])


class ProfileResponse(BaseModel):
    id: int
    name: str
    email: str | None
    avatar_letter: str
    workspace_name: str = "Personal account"
    workspace_plan: str = "Free"


@router.get("/", response_model=ProfileResponse)
async def get_profile(
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    if current_user:
        name = f"{current_user.firstName} {current_user.lastName}"
        return ProfileResponse(
            id=current_user.id,
            name=name,
            email=current_user.email or "admin@mayda.app",
            avatar_letter=current_user.firstName[0].upper() if current_user.firstName else "A",
        )

    # Fallback: get admin user from DB
    result = await db.execute(select(User).where(User.role == "ADMIN").limit(1))
    admin = result.scalar_one_or_none()
    if admin:
        name = f"{admin.firstName} {admin.lastName}"
        return ProfileResponse(
            id=admin.id,
            name=name,
            email=admin.email or "admin@mayda.app",
            avatar_letter=admin.firstName[0].upper() if admin.firstName else "A",
        )

    return ProfileResponse(
        id=1,
        name="Admin User",
        email="admin@mayda.app",
        avatar_letter="A",
    )
