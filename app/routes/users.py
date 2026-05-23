from fastapi import APIRouter, Depends

from app.core.database import get_db_session
from app.middleware.roles import get_current_user
from app.models.user import PushTokenResponse, PushTokenUpsertRequest


router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/me/push-token", response_model=PushTokenResponse)
async def register_push_token(
    push_token: PushTokenUpsertRequest,
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Register or transfer a mobile push token for the current user."""

    existing_token = await db.pushtoken.find_unique(
        where={"token": push_token.token}
    )

    if existing_token:
        if existing_token.userId == current_user.id:
            if existing_token.platform != push_token.platform.value:
                existing_token = await db.pushtoken.update(
                    where={"id": existing_token.id},
                    data={"platform": push_token.platform.value},
                )
            return PushTokenResponse.model_validate(existing_token)

        await db.pushtoken.delete(where={"id": existing_token.id})

    created_token = await db.pushtoken.create(
        data={
            "userId": current_user.id,
            "token": push_token.token,
            "platform": push_token.platform.value,
        }
    )

    return PushTokenResponse.model_validate(created_token)


@router.delete("/me/push-token/{token}")
async def delete_push_token(
    token: str,
    current_user=Depends(get_current_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Remove a mobile push token for the current user."""

    await db.pushtoken.delete_many(
        where={
            "userId": current_user.id,
            "token": token,
        }
    )

    return {"message": "Push token removed"}
