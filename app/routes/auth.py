from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update
from app.models.sqlalchemy_models import User, RefreshToken
from app.models.auth import (
    UserLogin, UserRegister, TokenResponse, RefreshTokenRequest, 
    PasswordChange, UserResponse, UserUpdate, StaffLogin, 
    TempTokenResponse, OtpVerificationRequest
)
from app.auth.jwt import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, verify_token, create_temp_token, verify_temp_token
)
from app.utils.sms_service import SMSService
from app.core.config import settings
from app.core.database import get_db_session
from app.middleware.roles import (
    get_current_user, get_current_admin_user
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db_session)):

    existing_user = None
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()

    if not existing_user:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists"
        )

    if user_data.role.value in ["WAITER", "CHEF", "MANAGER"] and not user_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restaurant ID is required for staff roles"
        )

    hashed_password = get_password_hash(user_data.password)

    user = User(
        email=user_data.email,
        phone=user_data.phone,
        firstName=user_data.firstName,
        lastName=user_data.lastName,
        password=hashed_password,
        role=user_data.role.value,
        restaurantId=user_data.restaurantId
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/staff-login", response_model=TempTokenResponse)
async def staff_login(user_data: StaffLogin, db: AsyncSession = Depends(get_db_session)):

    result = await db.execute(select(User).where(User.phone == user_data.phone))
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password"
        )

    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )

    if user.role not in ["WAITER", "CHEF", "MANAGER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access only"
        )

    sms_service = SMSService()
    otp_result = await sms_service.send_otp(user.id, str(user.phone), "STAFF_AUTH")

    if not otp_result.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

    temp_token = create_temp_token(user.id, "2fa")

    return TempTokenResponse(
        tempToken=temp_token,
        message="OTP sent to your phone. Please verify to complete login.",
        expiresIn=300
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_and_login(otp_data: OtpVerificationRequest, db: AsyncSession = Depends(get_db_session)):

    payload = verify_temp_token(otp_data.tempToken, "2fa")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired temporary token"
        )

    user_id = int(payload.get("sub"))

    sms_service = SMSService()
    otp_valid = await sms_service.verify_otp(user_id, otp_data.otpCode, "STAFF_AUTH")

    if not otp_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP"
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(token=refresh_token, userId=user.id, expiresAt=expires_at)
    db.add(rt)
    await db.commit()
    await db.refresh(rt)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db_session)):

    user = None
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        user = result.scalar_one_or_none()
    elif user_data.phone:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/phone or password"
        )

    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(token=refresh_token, userId=user.id, expiresAt=expires_at)
    db.add(rt)
    await db.commit()
    await db.refresh(rt)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db_session)):

    payload = verify_token(token_data.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == token_data.refresh_token,
            RefreshToken.userId == int(user_id),
            RefreshToken.isRevoked == False
        )
    )
    stored_token = result.scalar_one_or_none()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or revoked"
        )

    user = await db.get(User, int(user_id))
    if not user or not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    new_access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    stored_token.isRevoked = True
    await db.commit()
    await db.refresh(stored_token)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(token=new_refresh_token, userId=user.id, expiresAt=expires_at)
    db.add(rt)
    await db.commit()
    await db.refresh(rt)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
async def logout(token_data: RefreshTokenRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):

    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.token == token_data.refresh_token,
            RefreshToken.userId == current_user.id,
            RefreshToken.isRevoked == False
        )
        .values(isRevoked=True)
    )
    await db.commit()

    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):

    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.userId == current_user.id,
            RefreshToken.isRevoked == False
        )
        .values(isRevoked=True)
    )
    await db.commit()

    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate, 
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):

    update_data = {}

    if user_update.email is not None:
        result = await db.execute(
            select(User).where(User.email == user_update.email, User.id != current_user.id)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already taken"
            )
        update_data["email"] = user_update.email

    if user_update.firstName is not None:
        update_data["firstName"] = user_update.firstName

    if user_update.lastName is not None:
        update_data["lastName"] = user_update.lastName

    if user_update.phone is not None:
        result = await db.execute(
            select(User).where(User.phone == user_update.phone, User.id != current_user.id)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already taken"
            )
        update_data["phone"] = user_update.phone

    if current_user.role.value == "ADMIN":
        if user_update.role is not None:
            update_data["role"] = user_update.role.value
        if user_update.isActive is not None:
            update_data["isActive"] = user_update.isActive
        if user_update.restaurantId is not None:
            update_data["restaurantId"] = user_update.restaurantId

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )

    updated_user = await db.get(User, current_user.id)
    for key, value in update_data.items():
        setattr(updated_user, key, value)
    await db.commit()
    await db.refresh(updated_user)

    return UserResponse.model_validate(updated_user)


@router.put("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):

    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    hashed_password = get_password_hash(password_data.new_password)

    user = await db.get(User, current_user.id)
    user.password = hashed_password
    await db.commit()
    await db.refresh(user)

    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.userId == current_user.id,
            RefreshToken.isRevoked == False
        )
        .values(isRevoked=True)
    )
    await db.commit()

    return {"message": "Password changed successfully. Please log in again."}


@router.get("/users", response_model=list[UserResponse])
async def get_all_users(current_user=Depends(get_current_admin_user), db: AsyncSession = Depends(get_db_session)):

    result = await db.execute(select(User).order_by(User.createdAt.desc()))
    users = result.scalars().all()

    return [UserResponse.model_validate(user) for user in users]


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user=Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
):

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    update_data = {}

    if user_update.email is not None:
        result = await db.execute(
            select(User).where(User.email == user_update.email, User.id != user_id)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already taken"
            )
        update_data["email"] = user_update.email

    if user_update.firstName is not None:
        update_data["firstName"] = user_update.firstName

    if user_update.lastName is not None:
        update_data["lastName"] = user_update.lastName

    if user_update.phone is not None:
        result = await db.execute(
            select(User).where(User.phone == user_update.phone, User.id != user_id)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already taken"
            )
        update_data["phone"] = user_update.phone

    if user_update.role is not None:
        update_data["role"] = user_update.role.value

    if user_update.isActive is not None:
        update_data["isActive"] = user_update.isActive

    if user_update.restaurantId is not None:
        update_data["restaurantId"] = user_update.restaurantId

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )

    updated_user = await db.get(User, user_id)
    for key, value in update_data.items():
        setattr(updated_user, key, value)
    await db.commit()
    await db.refresh(updated_user)

    return UserResponse.model_validate(updated_user)
