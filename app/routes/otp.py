from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import create_access_token, create_refresh_token
from app.core.database import get_db_session
from app.middleware.roles import get_current_user
from app.models.otp import (
    OtpSendResponse,
    OtpVerifyResponse,
    PaymentOtpRequest,
    PaymentOtpVerifyRequest,
    StaffLoginRequest,
    StaffOtpVerifyRequest,
)
from app.models.sqlalchemy_models import Order, User
from app.models.user import UserRole
from app.utils.sms_service import sms_service

router = APIRouter(prefix="/otp", tags=["OTP Authentication"])


@router.post("/staff/send", response_model=OtpSendResponse)
async def send_staff_otp(request: StaffLoginRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Send OTP to staff member for authentication.
    Only staff members (WAITER, CHEF, MANAGER, ADMIN) can receive OTP.
    """
    if not sms_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS service is not available",
        )

    try:
        # Find staff user by phone
        result = await db.execute(select(User).where(User.phone == request.phone))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Check if user is staff
        if user.role not in [
            UserRole.WAITER.value,
            UserRole.CHEF.value,
            UserRole.MANAGER.value,
            UserRole.ADMIN.value,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OTP authentication is only available for staff members",
            )

        if not user.isActive:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

        # Send OTP
        otp_result = await sms_service.send_otp(user.id, str(user.phone), "STAFF_AUTH")

        if otp_result.get("success", False):
            return OtpSendResponse(success=True, message="OTP sent successfully to your phone number")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP. Please try again.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending OTP: {str(e)}",
        )


@router.post("/staff/verify", response_model=OtpVerifyResponse)
async def verify_staff_otp(request: StaffOtpVerifyRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Verify OTP code for staff authentication and return access token.
    """
    if not sms_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS service is not available",
        )

    try:
        # Find staff user by phone
        stmt = select(User).options(selectinload(User.restaurant)).where(User.phone == request.phone)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Verify OTP
        is_valid = await sms_service.verify_otp(user.id, request.code, "STAFF_AUTH")

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code",
            )

        # Create access token
        access_token_expires = timedelta(minutes=30)  # You can adjust this
        access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

        # Create refresh token
        create_refresh_token(user.id, db)

        # Return user info and token
        user_info = {
            "id": user.id,
            "email": user.email,
            "phone": user.phone,
            "firstName": user.firstName,
            "lastName": user.lastName,
            "role": user.role,
            "restaurantId": user.restaurantId,
            "restaurant": {"id": user.restaurant.id, "name": user.restaurant.name} if user.restaurant else None,
        }

        return OtpVerifyResponse(
            success=True,
            message="OTP verified successfully",
            accessToken=access_token,
            user=user_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying OTP: {str(e)}",
        )


@router.post("/payment/send", response_model=OtpSendResponse)
async def send_payment_otp(
    request: PaymentOtpRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Send OTP for payment confirmation.
    User must be authenticated and own the order.
    """
    if not sms_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS service is not available",
        )

    try:
        # Get order and validate ownership
        stmt = select(Order).options(selectinload(Order.user)).where(Order.id == request.orderId)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        # Check ownership (unless staff)
        if current_user.role == "CLIENT" and order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only request OTP for your own orders",
            )

        # Check if order is already paid
        if order.paymentStatus == "PAID":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is already paid")

        # Send OTP to order owner's phone
        target_user = order.user if order.user else current_user
        otp_result = await sms_service.send_otp(target_user.id, str(target_user.phone), "PAYMENT_CONFIRMATION")

        if otp_result.get("success", False):
            return OtpSendResponse(
                success=True,
                message="Payment confirmation OTP sent to order owner's phone",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP. Please try again.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending payment OTP: {str(e)}",
        )


@router.post("/payment/verify")
async def verify_payment_otp(
    request: PaymentOtpVerifyRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Verify OTP for payment confirmation and mark order as paid.
    """
    if not sms_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS service is not available",
        )

    try:
        # Get order and validate
        stmt = select(Order).options(selectinload(Order.user)).where(Order.id == request.orderId)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        # Check ownership (unless staff)
        if current_user.role == "CLIENT" and order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only verify OTP for your own orders",
            )

        # Verify OTP
        target_user = order.user if order.user else current_user
        is_valid = await sms_service.verify_otp(target_user.id, request.code, "PAYMENT_CONFIRMATION")

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code",
            )

        # Update order payment status
        order.paymentStatus = "PAID"
        await db.commit()

        return {
            "success": True,
            "message": "Payment confirmed successfully via OTP",
            "orderId": request.orderId,
            "paymentStatus": "PAID",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying payment OTP: {str(e)}",
        )
