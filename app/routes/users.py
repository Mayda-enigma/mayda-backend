from fastapi import APIRouter, Depends
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.middleware.roles import get_current_user
from app.models.sqlalchemy_models import PushToken, User
from app.models.user import PushTokenResponse, PushTokenUpsertRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/me/push-token", response_model=PushTokenResponse)
async def register_push_token(
    push_token: PushTokenUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Register or transfer a mobile push token for the current user."""

    existing_token = (
        await db.execute(select(PushToken).where(PushToken.token == push_token.token))
    ).scalar_one_or_none()

    if existing_token:
        if existing_token.userId == current_user.id:
            if existing_token.platform != push_token.platform.value:
                existing_token.platform = push_token.platform.value
                await db.commit()
                await db.refresh(existing_token)
            return PushTokenResponse.model_validate(existing_token)

        await db.delete(existing_token)
        await db.commit()

    created_token = PushToken(
        userId=current_user.id,
        token=push_token.token,
        platform=push_token.platform.value,
    )
    db.add(created_token)
    await db.commit()
    await db.refresh(created_token)

    return PushTokenResponse.model_validate(created_token)


@router.delete("/me/push-token/{token}")
async def delete_push_token(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Remove a mobile push token for the current user."""

    await db.execute(
        sa_delete(PushToken).where(
            PushToken.userId == current_user.id,
            PushToken.token == token,
        )
    )
    await db.commit()

    return {"message": "Push token removed"}
