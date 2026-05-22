from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.reservation import (
    ReservationCreate, ReservationUpdate, ReservationResponse, ReservationListResponse,
    PublicReservationCreate, ReservationStatusUpdate, ReservationStatus,
    ReservationAvailabilityRequest, ReservationAvailabilityResponse, AvailableTable
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_staff_user, get_current_user, get_current_user_optional
)


router = APIRouter(prefix="/reservations", tags=["Reservations"])


# ==================== PUBLIC RESERVATION ENDPOINTS ====================

@router.post("/availability", response_model=ReservationAvailabilityResponse)
async def check_availability(request: ReservationAvailabilityRequest):
    """
    Check table availability for a specific time slot (Public endpoint).
    
    This endpoint is public to allow potential customers to check availability
    before deciding to make a reservation through the app (which requires authentication).
    """
    db = get_db()
    
    # Validate restaurant exists and is active
    restaurant = await db.restaurant.find_unique(where={"id": request.restaurantId})
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Get all active tables for the restaurant
    all_tables = await db.table.find_many(
        where={
            "restaurantId": request.restaurantId,
            "isActive": True
        },
        order={"number": "asc"}
    )
    
    if not all_tables:
        return ReservationAvailabilityResponse(
            available=False,
            availableTables=[],
            message="No tables available at this restaurant"
        )
    
    # Filter tables by party size if specified
    suitable_tables = all_tables
    if request.partySize:
        suitable_tables = [table for table in all_tables if table.capacity >= request.partySize]
        
        if not suitable_tables:
            return ReservationAvailabilityResponse(
                available=False,
                availableTables=[],
                message=f"No tables available for party size of {request.partySize}"
            )
    
    # Check for conflicting reservations
    conflicting_reservations = await db.reservation.find_many(
        where={
            "restaurantId": request.restaurantId,
            "status": {"in": ["PENDING", "CONFIRMED"]},
            "OR": [
                {
                    "AND": [
                        {"reservationStart": {"lte": request.reservationStart}},
                        {"reservationEnd": {"gt": request.reservationStart}}
                    ]
                },
                {
                    "AND": [
                        {"reservationStart": {"lt": request.reservationEnd}},
                        {"reservationEnd": {"gte": request.reservationEnd}}
                    ]
                },
                {
                    "AND": [
                        {"reservationStart": {"gte": request.reservationStart}},
                        {"reservationEnd": {"lte": request.reservationEnd}}
                    ]
                }
            ]
        }
    )
    
    # Get table IDs that are reserved during the requested time
    reserved_table_ids = set()
    for reservation in conflicting_reservations:
        if reservation.tableId:
            reserved_table_ids.add(reservation.tableId)
    
    # Filter out reserved tables
    available_tables = [
        table for table in suitable_tables 
        if table.id not in reserved_table_ids
    ]
    
    if not available_tables:
        return ReservationAvailabilityResponse(
            available=False,
            availableTables=[],
            message="No tables available for the requested time slot"
        )
    
    return ReservationAvailabilityResponse(
        available=True,
        availableTables=[AvailableTable.model_validate(table) for table in available_tables],
        message=f"{len(available_tables)} table(s) available"
    )


@router.post("/public", response_model=ReservationResponse)
async def create_public_reservation(
    reservation_data: PublicReservationCreate,
    current_user = Depends(get_current_staff_user)
):
    """Create reservation without customer authentication (Staff only - for phone bookings/walk-ins)."""
    db = get_db()
    
    # Check permissions - only staff can create public reservations
    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only restaurant staff can create public reservations"
        )
    
    # Staff can only create reservations for their own restaurant (except admins)
    if current_user.role != "ADMIN" and current_user.restaurantId != reservation_data.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create reservations for your own restaurant"
        )
    
    # Validate restaurant
    restaurant = await db.restaurant.find_unique(where={"id": reservation_data.restaurantId})
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Validate table if specified
    if reservation_data.tableId:
        table = await db.table.find_unique(
            where={
                "id": reservation_data.tableId,
                "restaurantId": reservation_data.restaurantId
            }
        )
        if not table or not table.isActive:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found or inactive"
            )
        
        # Check table availability
        availability_request = ReservationAvailabilityRequest(
            restaurantId=reservation_data.restaurantId,
            reservationStart=reservation_data.reservationStart,
            reservationEnd=reservation_data.reservationEnd
        )
        availability = await check_availability(availability_request)
        
        if not availability.available or not any(t.id == reservation_data.tableId for t in availability.availableTables):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected table is not available for the requested time slot"
            )
    
    try:
        # Create guest user or find existing one
        guest_user = await db.user.find_first(
            where={"phone": int(reservation_data.customerPhone)}
        )
        
        if not guest_user:
            # Create temporary guest user
            guest_user = await db.user.create(
                data={
                    "phone": int(reservation_data.customerPhone),
                    "firstName": reservation_data.customerName.split()[0] if reservation_data.customerName else "Guest",
                    "lastName": " ".join(reservation_data.customerName.split()[1:]) if len(reservation_data.customerName.split()) > 1 else "",
                    "email": reservation_data.customerEmail,
                    "role": "CLIENT",
                    "password": "temp_password",  # Temporary password for guest users
                    "isActive": True
                }
            )
        
        # Create reservation
        reservation = await db.reservation.create(
            data={
                "userId": guest_user.id,
                "restaurantId": reservation_data.restaurantId,
                "tableId": reservation_data.tableId,
                "reservationStart": reservation_data.reservationStart,
                "reservationEnd": reservation_data.reservationEnd,
                "status": ReservationStatus.PENDING.value
            }
        )
        
        # Fetch complete reservation with relations
        complete_reservation = await db.reservation.find_unique(
            where={"id": reservation.id},
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True,
                        "phone": True,
                        "email": True
                    }
                },
                "table": True,
                "restaurant": {
                    "select": {
                        "name": True,
                        "phone": True,
                        "email": True
                    }
                }
            }
        )
        
        return ReservationResponse.model_validate(complete_reservation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating reservation: {str(e)}"
        )


# ==================== AUTHENTICATED RESERVATION ENDPOINTS ====================

@router.post("/", response_model=ReservationResponse)
async def create_reservation(
    reservation_data: ReservationCreate,
    current_user = Depends(get_current_user)
):
    """Create reservation for authenticated user using their stored profile information."""
    db = get_db()
    
    # Get user's complete profile for contact information
    user_profile = await db.user.find_unique(
        where={"id": current_user.id}
    )
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Ensure user has complete contact information for reservations
    if not user_profile.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required for reservations. Please update your profile."
        )
    
    # Validate restaurant
    restaurant = await db.restaurant.find_unique(where={"id": reservation_data.restaurantId})
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Validate table if specified
    if reservation_data.tableId:
        table = await db.table.find_unique(
            where={
                "id": reservation_data.tableId,
                "restaurantId": reservation_data.restaurantId
            }
        )
        if not table or not table.isActive:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found or inactive"
            )
        
        # Check table availability
        availability_request = ReservationAvailabilityRequest(
            restaurantId=reservation_data.restaurantId,
            reservationStart=reservation_data.reservationStart,
            reservationEnd=reservation_data.reservationEnd
        )
        availability = await check_availability(availability_request)
        
        if not availability.available or not any(t.id == reservation_data.tableId for t in availability.availableTables):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected table is not available for the requested time slot"
            )
    
    try:
        reservation = await db.reservation.create(
            data={
                "userId": current_user.id,
                "restaurantId": reservation_data.restaurantId,
                "tableId": reservation_data.tableId,
                "reservationStart": reservation_data.reservationStart,
                "reservationEnd": reservation_data.reservationEnd,
                "status": ReservationStatus.PENDING.value
            }
        )
        
        # Fetch complete reservation
        complete_reservation = await db.reservation.find_unique(
            where={"id": reservation.id},
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True,
                        "phone": True,
                        "email": True
                    }
                },
                "table": True,
                "restaurant": {
                    "select": {
                        "name": True,
                        "phone": True,
                        "email": True
                    }
                }
            }
        )
        
        return ReservationResponse.model_validate(complete_reservation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating reservation: {str(e)}"
        )


@router.get("/my-reservations", response_model=List[ReservationListResponse])
async def get_my_reservations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[ReservationStatus] = Query(None),
    current_user = Depends(get_current_user)
):
    """Get current user's reservations."""
    db = get_db()
    
    where_clause = {"userId": current_user.id}
    if status:
        where_clause["status"] = status.value
    
    reservations = await db.reservation.find_many(
        where=where_clause,
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                    "phone": True
                }
            },
            "table": {"select": {"number": True}},
            "restaurant": {"select": {"name": True}}
        },
        skip=skip,
        take=limit,
        order={"reservationStart": "desc"}
    )
    
    # Format response
    reservation_list = []
    for reservation in reservations:
        reservation_dict = reservation.__dict__.copy()
        reservation_dict["customerName"] = f"{reservation.user.firstName} {reservation.user.lastName}" if reservation.user else None
        reservation_dict["customerPhone"] = str(reservation.user.phone) if reservation.user else None
        reservation_dict["tableNumber"] = reservation.table.number if reservation.table else None
        reservation_dict["restaurantName"] = reservation.restaurant.name if reservation.restaurant else None
        reservation_list.append(ReservationListResponse.model_validate(reservation_dict))
    
    return reservation_list


@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: int,
    current_user = Depends(get_current_user_optional)
):
    """Get reservation by ID. Users can only see their own reservations, staff can see restaurant reservations."""
    db = get_db()
    
    reservation = await db.reservation.find_unique(
        where={"id": reservation_id},
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                    "phone": True,
                    "email": True
                }
            },
            "table": True,
            "restaurant": {
                "select": {
                    "name": True,
                    "phone": True,
                    "email": True
                }
            }
        }
    )
    
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    
    # Check permissions
    if current_user:
        if current_user.role == "ADMIN":
            # Admin can see all reservations
            pass
        elif current_user.role in ["WAITER", "CHEF", "MANAGER"]:
            # Staff can see reservations from their restaurant
            if current_user.restaurantId != reservation.restaurantId:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view reservations from your restaurant"
                )
        else:
            # Regular users can only see their own reservations
            if reservation.userId != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own reservations"
                )
    
    return ReservationResponse.model_validate(reservation)


# ==================== STAFF RESERVATION MANAGEMENT ====================

@router.get("/restaurant/{restaurant_id}", response_model=List[ReservationListResponse])
async def get_restaurant_reservations(
    restaurant_id: int,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    status: Optional[ReservationStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_staff_user)
):
    """Get reservations for a restaurant (Staff only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view reservations from your own restaurant"
        )
    
    where_clause = {"restaurantId": restaurant_id}
    
    if status:
        where_clause["status"] = status.value
    
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())
            where_clause["reservationStart"] = {
                "gte": start_of_day,
                "lte": end_of_day
            }
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    
    reservations = await db.reservation.find_many(
        where=where_clause,
        include={
            "user": {
                "select": {
                    "firstName": True,
                    "lastName": True,
                    "phone": True
                }
            },
            "table": {"select": {"number": True}},
            "restaurant": {"select": {"name": True}}
        },
        skip=skip,
        take=limit,
        order={"reservationStart": "asc"}
    )
    
    # Format response
    reservation_list = []
    for reservation in reservations:
        reservation_dict = reservation.__dict__.copy()
        reservation_dict["customerName"] = f"{reservation.user.firstName} {reservation.user.lastName}" if reservation.user else None
        reservation_dict["customerPhone"] = str(reservation.user.phone) if reservation.user else None
        reservation_dict["tableNumber"] = reservation.table.number if reservation.table else None
        reservation_dict["restaurantName"] = reservation.restaurant.name if reservation.restaurant else None
        reservation_list.append(ReservationListResponse.model_validate(reservation_dict))
    
    return reservation_list


@router.patch("/{reservation_id}/status", response_model=ReservationResponse)
async def update_reservation_status(
    reservation_id: int,
    status_update: ReservationStatusUpdate,
    current_user = Depends(get_current_staff_user)
):
    """Update reservation status (Staff only)."""
    db = get_db()
    
    # Check if reservation exists
    reservation = await db.reservation.find_unique(where={"id": reservation_id})
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != reservation.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update reservations from your own restaurant"
        )
    
    try:
        updated_reservation = await db.reservation.update(
            where={"id": reservation_id},
            data={
                "status": status_update.status.value,
                "updatedAt": datetime.now()
            },
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True,
                        "phone": True,
                        "email": True
                    }
                },
                "table": True,
                "restaurant": {
                    "select": {
                        "name": True,
                        "phone": True,
                        "email": True
                    }
                }
            }
        )
        
        return ReservationResponse.model_validate(updated_reservation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating reservation status: {str(e)}"
        )


@router.put("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: int,
    reservation_update: ReservationUpdate,
    current_user = Depends(get_current_user)
):
    """Update reservation details (Customer or Staff)."""
    db = get_db()
    
    # Check if reservation exists
    reservation = await db.reservation.find_unique(where={"id": reservation_id})
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        # Regular users can only update their own reservations
        if reservation.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own reservations"
            )
        
        # Users can only update pending reservations
        if reservation.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You can only update pending reservations"
            )
    else:
        # Staff can only update reservations from their restaurant
        if current_user.role != "ADMIN" and current_user.restaurantId != reservation.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update reservations from your own restaurant"
            )
    
    # Prepare update data
    update_data = {}
    if reservation_update.tableId is not None:
        # Validate new table
        table = await db.table.find_unique(
            where={
                "id": reservation_update.tableId,
                "restaurantId": reservation.restaurantId
            }
        )
        if not table or not table.isActive:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found or inactive"
            )
        update_data["tableId"] = reservation_update.tableId
    
    if reservation_update.reservationStart:
        update_data["reservationStart"] = reservation_update.reservationStart
    
    if reservation_update.reservationEnd:
        update_data["reservationEnd"] = reservation_update.reservationEnd
    
    if update_data:
        update_data["updatedAt"] = datetime.now()
    
    try:
        updated_reservation = await db.reservation.update(
            where={"id": reservation_id},
            data=update_data,
            include={
                "user": {
                    "select": {
                        "firstName": True,
                        "lastName": True,
                        "phone": True,
                        "email": True
                    }
                },
                "table": True,
                "restaurant": {
                    "select": {
                        "name": True,
                        "phone": True,
                        "email": True
                    }
                }
            }
        )
        
        return ReservationResponse.model_validate(updated_reservation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating reservation: {str(e)}"
        )


@router.delete("/{reservation_id}")
async def cancel_reservation(
    reservation_id: int,
    current_user = Depends(get_current_user)
):
    """Cancel reservation (Customer or Staff)."""
    db = get_db()
    
    # Check if reservation exists
    reservation = await db.reservation.find_unique(where={"id": reservation_id})
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER", "WAITER"]:
        # Regular users can only cancel their own reservations
        if reservation.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel your own reservations"
            )
    else:
        # Staff can only cancel reservations from their restaurant
        if current_user.role != "ADMIN" and current_user.restaurantId != reservation.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel reservations from your own restaurant"
            )
    
    # Check if reservation can be cancelled
    if reservation.status in ["CANCELLED", "COMPLETED", "NO_SHOW"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel reservation with status: {reservation.status}"
        )
    
    try:
        await db.reservation.update(
            where={"id": reservation_id},
            data={
                "status": ReservationStatus.CANCELLED.value,
                "updatedAt": datetime.now()
            }
        )
        
        return {"message": "Reservation cancelled successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error cancelling reservation: {str(e)}"
        )
