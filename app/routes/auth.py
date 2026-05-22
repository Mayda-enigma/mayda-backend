from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta
from app.models.auth import (
    UserLogin, UserRegister, TokenResponse, RefreshTokenRequest, 
    PasswordChange, UserResponse, UserUpdate, StaffLogin, 
    TempTokenResponse, OtpVerificationRequest
)
from app.auth.jwt import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, verify_token, create_temp_token, verify_temp_token
)
from app.utils.sms_service_debug import SMSService
from app.core.config import settings
from app.core.database import get_db
from app.middleware.roles import (
    get_current_user, get_current_admin_user, get_current_manager_or_admin
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister):
    """Register a new user."""
    db = get_db()
    
    # Check if user already exists
    existing_user = None
    if user_data.email:
        existing_user = await db.user.find_first(
            where={"email": user_data.email}
        )
    
    if not existing_user:
        existing_user = await db.user.find_first(
            where={"phone": user_data.phone}
        )
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists"
        )
    
    # Validate restaurant association for staff roles
    if user_data.role.value in ["WAITER", "CHEF", "MANAGER"] and not user_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restaurant ID is required for staff roles"
        )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    user = await db.user.create(
        data={
            "email": user_data.email,
            "phone": user_data.phone,
            "firstName": user_data.firstName,
            "lastName": user_data.lastName,
            "password": hashed_password,
            "role": user_data.role.value,
            "restaurantId": user_data.restaurantId
        }
    )
    
    return UserResponse.model_validate(user)


@router.post("/staff-login", response_model=TempTokenResponse)
async def staff_login(user_data: StaffLogin):
    """Staff login with 2FA - returns temporary token."""
    db = get_db()
    
    # Find user by phone
    user = await db.user.find_unique(where={"phone": user_data.phone})
    
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
    
    # Check if user is staff
    if user.role not in ["WAITER", "CHEF", "MANAGER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access only"
        )
    
    # Send OTP
    sms_service = SMSService()
    otp_result = await sms_service.send_otp(user.id, str(user.phone), "STAFF_AUTH")
    
    if not otp_result.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )
    
    # Create temporary token
    temp_token = create_temp_token(user.id, "2fa")
    
    return TempTokenResponse(
        tempToken=temp_token,
        message="OTP sent to your phone. Please verify to complete login.",
        expiresIn=300  # 5 minutes
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_and_login(otp_data: OtpVerificationRequest):
    """Verify OTP and complete staff login."""
    db = get_db()
    
    # Verify temporary token
    payload = verify_temp_token(otp_data.tempToken, "2fa")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired temporary token"
        )
    
    user_id = int(payload.get("sub"))
    
    # Verify OTP
    sms_service = SMSService()
    otp_valid = await sms_service.verify_otp(user_id, otp_data.otpCode, "STAFF_AUTH")
    
    if not otp_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP"
        )
    
    # Get user
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Store refresh token in database
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await db.refreshtoken.create(
        data={
            "token": refresh_token,
            "userId": user.id,
            "expiresAt": expires_at
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Authenticate regular user and return access token (customers only)."""
    db = get_db()
    
    # Find user by email or phone
    user = None
    if user_data.email:
        user = await db.user.find_unique(where={"email": user_data.email})
    elif user_data.phone:
        user = await db.user.find_unique(where={"phone": user_data.phone})
    
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
    
    # For staff users, redirect to 2FA login
    if user.role in ["WAITER", "CHEF", "MANAGER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff users must use /auth/staff-login for 2FA authentication"
        )
    
    # Create tokens for customer users
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Store refresh token in database
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await db.refreshtoken.create(
        data={
            "token": refresh_token,
            "userId": user.id,
            "expiresAt": expires_at
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    db = get_db()
    
    # Verify refresh token
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
    
    # Check if refresh token exists in database and is not revoked
    stored_token = await db.refreshtoken.find_first(
        where={
            "token": token_data.refresh_token,
            "userId": int(user_id),
            "isRevoked": False
        }
    )
    
    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or revoked"
        )
    
    # Get user
    user = await db.user.find_unique(where={"id": int(user_id)})
    if not user or not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    new_access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Revoke old refresh token and create new one
    await db.refreshtoken.update(
        where={"id": stored_token.id},
        data={"isRevoked": True}
    )
    
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await db.refreshtoken.create(
        data={
            "token": new_refresh_token,
            "userId": user.id,
            "expiresAt": expires_at
        }
    )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
async def logout(token_data: RefreshTokenRequest, current_user=Depends(get_current_user)):
    """Logout user by revoking refresh token."""
    db = get_db()
    
    # Revoke the refresh token
    await db.refreshtoken.update_many(
        where={
            "token": token_data.refresh_token,
            "userId": current_user.id,
            "isRevoked": False
        },
        data={"isRevoked": True}
    )
    
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all(current_user=Depends(get_current_user)):
    """Logout user from all devices by revoking all refresh tokens."""
    db = get_db()
    
    # Revoke all refresh tokens for the user
    await db.refreshtoken.update_many(
        where={
            "userId": current_user.id,
            "isRevoked": False
        },
        data={"isRevoked": True}
    )
    
    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate, 
    current_user=Depends(get_current_user)
):
    """Update current user information."""
    db = get_db()
    
    update_data = {}
    
    # Regular users can only update basic info
    if user_update.email is not None:
        # Check if email is already taken by another user
        existing_user = await db.user.find_first(
            where={
                "email": user_update.email,
                "id": {"not": current_user.id}
            }
        )
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
        # Check if phone is already taken by another user
        existing_user = await db.user.find_first(
            where={
                "phone": user_update.phone,
                "id": {"not": current_user.id}
            }
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already taken"
            )
        update_data["phone"] = user_update.phone
    
    # Only allow role/admin updates if user is admin
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
    
    updated_user = await db.user.update(
        where={"id": current_user.id},
        data=update_data
    )
    
    return UserResponse.model_validate(updated_user)


@router.put("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user=Depends(get_current_user)
):
    """Change user password."""
    db = get_db()
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Hash new password
    hashed_password = get_password_hash(password_data.new_password)
    
    # Update password
    await db.user.update(
        where={"id": current_user.id},
        data={"password": hashed_password}
    )
    
    # Revoke all refresh tokens to force re-login
    await db.refreshtoken.update_many(
        where={
            "userId": current_user.id,
            "isRevoked": False
        },
        data={"isRevoked": True}
    )
    
    return {"message": "Password changed successfully. Please log in again."}


# Admin routes
@router.get("/users", response_model=list[UserResponse])
async def get_all_users(current_user=Depends(get_current_admin_user)):
    """Get all users (Admin only)."""
    db = get_db()
    
    users = await db.user.find_many(
        order={"createdAt": "desc"}
    )
    
    return [UserResponse.model_validate(user) for user in users]


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user=Depends(get_current_admin_user)
):
    """Update any user (Admin only)."""
    db = get_db()
    
    # Check if user exists
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = {}
    
    if user_update.email is not None:
        # Check if email is already taken by another user
        existing_user = await db.user.find_first(
            where={
                "email": user_update.email,
                "id": {"not": user_id}
            }
        )
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
        # Check if phone is already taken by another user
        existing_user = await db.user.find_first(
            where={
                "phone": user_update.phone,
                "id": {"not": user_id}
            }
        )
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
    
    updated_user = await db.user.update(
        where={"id": user_id},
        data=update_data
    )
    
    return UserResponse.model_validate(updated_user)
