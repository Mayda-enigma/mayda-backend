from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
import requests
from datetime import datetime
from app.models.payment import (
    PaymentCreate, PaymentResponse, PaymentInitiateRequest, 
    PaymentInitiateResponse, PaymentStatusResponse, PaymentListResponse,
    GUIDINI_PAY_URL, GUIDINI_PAY_HEADERS
)
from app.core.database import get_db
from app.middleware.roles import get_current_user, get_current_staff_user


router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/initiate-with-otp", response_model=PaymentInitiateResponse)
async def initiate_payment_with_otp(
    payment_request: PaymentInitiateRequest,
    current_user=Depends(get_current_user)
):
    """
    Initiate payment with OTP verification for added security.
    Sends OTP to user's phone before processing payment.
    """
    from app.utils.sms_service import sms_service
    
    if not sms_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS service is not available for secure payments"
        )
    
    db = get_db()
    
    # Check if Guidini Pay is configured
    if not GUIDINI_PAY_HEADERS.get("x-app-key") or not GUIDINI_PAY_HEADERS.get("x-app-secret"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured. Please contact support."
        )
    
    try:
        # Get the order and validate it belongs to the user
        order = await db.order.find_unique(
            where={"id": payment_request.orderId},
            include={"user": True, "restaurant": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check if user owns the order (unless they're staff)
        if current_user.role == "CLIENT" and order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only pay for your own orders"
            )
        
        # Check if order is already paid
        if order.paymentStatus == "PAID":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already paid"
            )
        
        # Send OTP for payment confirmation
        otp_code = await sms_service.send_otp(current_user.id, str(current_user.phone), "PAYMENT_CONFIRMATION")
        
        if not otp_code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP for payment verification"
            )
        
        return PaymentInitiateResponse(
            success=True,
            message="OTP sent to your phone. Please verify to proceed with payment.",
            paymentId=None,
            transactionId=None,
            formUrl=None,
            amount=str(order.totalAmount)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate secure payment: {str(e)}"
        )


@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate_payment(
    payment_request: PaymentInitiateRequest,
    current_user=Depends(get_current_user)
):
    """
    Initiate a payment for an order using Guidini Pay.
    This will create a payment record and return the payment form URL.
    """
    db = get_db()
    
    # Check if Guidini Pay is configured
    if not GUIDINI_PAY_HEADERS.get("x-app-key") or not GUIDINI_PAY_HEADERS.get("x-app-secret"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured. Please contact support."
        )
    
    try:
        # Get the order and validate it belongs to the user
        order = await db.order.find_unique(
            where={"id": payment_request.orderId},
            include={"user": True, "restaurant": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check if user owns the order (unless they're staff)
        if current_user.role == "CLIENT" and order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only pay for your own orders"
            )
        
        # Check if order is already paid
        if order.paymentStatus == "PAID":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already paid"
            )
        
        # Check if payment already exists for this order
        existing_payment = await db.payments.find_unique(
            where={"orderId": payment_request.orderId}
        )
        
        if existing_payment:
            return PaymentInitiateResponse(
                success=False,
                message="Payment already exists for this order",
                error="PAYMENT_EXISTS"
            )
        
        # Prepare Guidini Pay request
        guidini_data = {
            "amount": str(int(order.totalAmount * 100)),  # Convert to cents
            "language": payment_request.language
        }
        
        # Call Guidini Pay API
        response = requests.post(
            GUIDINI_PAY_URL,
            json=guidini_data,
            headers=GUIDINI_PAY_HEADERS,
            timeout=30
        )
        
        # Try to parse the response regardless of status code
        try:
            guidini_response = response.json()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Invalid JSON response from payment gateway. Status: {response.status_code}, Response: {response.text}"
            )
        
        # Check if response has expected structure
        if "data" not in guidini_response:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected payment gateway response format: {guidini_response}"
            )
        
        # Extract transaction data
        transaction_data = guidini_response["data"]
        transaction_id = transaction_data["id"]
        
        # Extract form_url and clean it if it has markdown brackets
        form_url = transaction_data["attributes"]["form_url"]
        # Remove markdown brackets if present: [url](url) -> url
        if form_url.startswith('[') and '](' in form_url and form_url.endswith(')'):
            # Extract URL from markdown format [text](url)
            start = form_url.find('](') + 2
            end = form_url.rfind(')')
            form_url = form_url[start:end]
        
        amount = transaction_data["attributes"]["amount"]
        
        # Create payment record in database
        payment = await db.payments.create(
            data={
                "paymentId": transaction_id,
                "orderId": payment_request.orderId
            }
        )
        
        return PaymentInitiateResponse(
            success=True,
            paymentId=str(payment.id),
            transactionId=transaction_id,
            formUrl=form_url,
            amount=amount,
            message="Payment initiated successfully"
        )
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment gateway connection error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate payment: {str(e)}"
        )


@router.get("/receipt/{order_number}")
async def get_payment_receipt(
    order_number: str,
    current_user=Depends(get_current_user)
):
    """
    Get payment receipt from Guidini Pay by order number.
    Routes the request to Guidini Pay receipt API and returns the response.
    """
    db = get_db()
    
    try:
        # First, find the order by orderNumber to validate access
        order = await db.order.find_unique(
            where={"orderNumber": order_number},
            include={"user": True, "restaurant": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check authorization: user owns the order OR user is staff of the restaurant
        is_owner = current_user.role == "CLIENT" and order.userId == current_user.id
        is_restaurant_staff = (
            current_user.role in ["WAITER", "CHEF", "MANAGER", "ADMIN"] and
            current_user.restaurantId == order.restaurantId
        )
        
        if not (is_owner or is_restaurant_staff):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only download receipts for your own orders or your restaurant's orders"
            )
        
        # Make request to Guidini Pay receipt API
        response = requests.get(
            "https://epay.guiddini.dz/api/payment/receipt",
            json={"order_number": order_number},
            headers=GUIDINI_PAY_HEADERS,
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment gateway error"
            )
        
        # Return the Guidini Pay receipt response directly
        return response.json()
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment gateway connection error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment receipt: {str(e)}"
        )


@router.get("/show/{order_number}")
async def show_payment_status(
    order_number: str,
    current_user=Depends(get_current_user)
):
    """
    Get payment status from Guidini Pay by order number.
    Routes the request to Guidini Pay and returns the response.
    """
    db = get_db()
    
    try:
        # First, find the order by orderNumber to validate access
        order = await db.order.find_unique(
            where={"orderNumber": order_number},
            include={"user": True, "restaurant": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check authorization: user owns the order OR user is staff of the restaurant
        is_owner = current_user.role == "CLIENT" and order.userId == current_user.id
        is_restaurant_staff = (
            current_user.role in ["WAITER", "CHEF", "MANAGER", "ADMIN"] and
            current_user.restaurantId == order.restaurantId
        )
        
        if not (is_owner or is_restaurant_staff):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view payment status for your own orders or your restaurant's orders"
            )
        
        # Make request to Guidini Pay show API
        response = requests.get(
            "https://epay.guiddini.dz/api/payment/show",
            json={"order_number": order_number},
            headers=GUIDINI_PAY_HEADERS,
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment gateway error"
            )
        
        # Return the Guidini Pay response directly
        return response.json()
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment gateway connection error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment status: {str(e)}"
        )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    current_user=Depends(get_current_user)
):
    """Get payment details by ID."""
    db = get_db()
    
    try:
        payment = await db.payments.find_unique(
            where={"id": payment_id},
            include={
                "order": {
                    "include": {
                        "user": True,
                        "restaurant": True
                    }
                }
            }
        )
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Check if user owns the payment (unless they're staff)
        if current_user.role == "CLIENT" and payment.order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own payments"
            )
        
        return PaymentResponse(
            id=payment.id,
            paymentId=payment.paymentId,
            orderId=payment.orderId,
            order={
                "orderNumber": payment.order.orderNumber,
                "totalAmount": payment.order.totalAmount,
                "paymentStatus": payment.order.paymentStatus,
                "restaurant": {
                    "name": payment.order.restaurant.name
                }
            },
            createdAt=payment.createdAt
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment: {str(e)}"
        )


@router.get("/order/{order_id}", response_model=Optional[PaymentStatusResponse])
async def get_payment_by_order(
    order_id: int,
    current_user=Depends(get_current_user)
):
    """Get payment status for a specific order."""
    db = get_db()
    
    try:
        # Get the order first to validate access
        order = await db.order.find_unique(
            where={"id": order_id},
            include={"user": True, "restaurant": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check if user owns the order (unless they're staff)
        if current_user.role == "CLIENT" and order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view payments for your own orders"
            )
        
        # Get the payment for this order
        payment = await db.payments.find_unique(
            where={"orderId": order_id}
        )
        
        if not payment:
            return None
        
        return PaymentStatusResponse(
            id=payment.id,
            paymentId=payment.paymentId,
            orderId=payment.orderId,
            orderNumber=order.orderNumber,
            amount=order.totalAmount,
            status=order.paymentStatus,
            createdAt=payment.createdAt
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment status: {str(e)}"
        )


@router.get("/", response_model=PaymentListResponse)
async def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    restaurant_id: Optional[int] = Query(None),
    current_user=Depends(get_current_staff_user)
):
    """
    List payments (staff only).
    Filter by restaurant if specified.
    """
    db = get_db()
    
    try:
        # Build where clause
        where_clause = {}
        
        # Filter by restaurant if specified
        if restaurant_id:
            # Validate staff has access to this restaurant
            if current_user.restaurantId and current_user.restaurantId != restaurant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view payments for your restaurant"
                )
            where_clause["order"] = {"restaurantId": restaurant_id}
        elif current_user.restaurantId:
            # Staff can only see their restaurant's payments
            where_clause["order"] = {"restaurantId": current_user.restaurantId}
        
        # Get total count
        total = await db.payments.count(where=where_clause)
        
        # Get payments with pagination
        payments = await db.payments.find_many(
            where=where_clause,
            include={
                "order": {
                    "include": {
                        "user": True,
                        "restaurant": True
                    }
                }
            },
            skip=(page - 1) * page_size,
            take=page_size,
            order_by={"createdAt": "desc"}
        )
        
        # Format response
        payment_list = []
        for payment in payments:
            payment_list.append(PaymentStatusResponse(
                id=payment.id,
                paymentId=payment.paymentId,
                orderId=payment.orderId,
                orderNumber=payment.order.orderNumber,
                amount=payment.order.totalAmount,
                status=payment.order.paymentStatus,
                createdAt=payment.createdAt
            ))
        
        return PaymentListResponse(
            payments=payment_list,
            total=total,
            page=page,
            pageSize=page_size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payments: {str(e)}"
        )


@router.get("/callback")
async def payment_callback(order_number: str = Query(...)):
    """
    Payment confirmation callback from Guidini Pay.
    Called when payment is confirmed with order_number as query parameter.
    """
    db = get_db()
    
    try:
        # Find the order by orderNumber
        order = await db.order.find_unique(
            where={"orderNumber": order_number},
            include={"restaurant": True, "user": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Update the order payment status to PAID
        updated_order = await db.order.update(
            where={"orderNumber": order_number},
            data={"paymentStatus": "PAID"}
        )
        
        # You can redirect to a success page or return confirmation
        return {
            "success": True,
            "message": "Payment confirmed successfully",
            "orderNumber": order_number,
            "orderId": order.id,
            "paymentStatus": "PAID",
            "totalAmount": order.totalAmount,
            "restaurant": order.restaurant.name if order.restaurant else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process payment confirmation: {str(e)}"
        )


@router.post("/webhook/guidini")
async def guidini_webhook():
    """
    Webhook endpoint for Guidini Pay payment status updates.
    This should be called by Guidini Pay when payment status changes.
    """
    # TODO: Implement webhook handling
    # This would typically:
    # 1. Verify the webhook signature
    # 2. Parse the payment status update
    # 3. Update the order's payment status in the database
    # 4. Send notifications if needed
    
    return {"status": "received"}


@router.put("/orders/{order_id}/payment-status")
async def update_payment_status(
    order_id: int,
    new_status: str,
    current_user=Depends(get_current_staff_user)
):
    """
    Manually update payment status (staff only).
    This is for manual payment methods like cash.
    """
    db = get_db()
    
    try:
        # Validate the new status
        valid_statuses = ["PENDING", "PAID", "FAILED", "REFUNDED"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payment status. Must be one of: {valid_statuses}"
            )
        
        # Get the order
        order = await db.order.find_unique(
            where={"id": order_id},
            include={"restaurant": True}
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check if staff has access to this restaurant
        if current_user.restaurantId and current_user.restaurantId != order.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update payments for your restaurant's orders"
            )
        
        # Update the order's payment status
        updated_order = await db.order.update(
            where={"id": order_id},
            data={"paymentStatus": new_status}
        )
        
        return {
            "success": True,
            "message": f"Payment status updated to {new_status}",
            "orderId": order_id,
            "paymentStatus": new_status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment status: {str(e)}"
        )
