from fastapi import APIRouter, HTTPException, status, Depends, Query
import secrets
import string
from typing import List
from app.auth.jwt import get_password_hash
from app.models.restaurant import (
    RestaurantCreate, RestaurantUpdate, RestaurantResponse, 
    RestaurantListResponse
)
from app.models.staff import (
    StaffInviteRequest,
    StaffInviteResponse,
    StaffListResponse,
    StaffResponse,
    StaffUpdate,
)
from app.core.database import get_db_session
from app.middleware.roles import (
    get_current_admin_user, get_current_manager_or_admin,
    get_current_user_optional, require_restaurant_staff
)
from app.models.user import UserRole
from app.utils.sms_service import SMSService, sms_service


router = APIRouter(prefix="/restaurants", tags=["Restaurants"])

STAFF_ROLES = {UserRole.WAITER, UserRole.CHEF, UserRole.MANAGER}


def is_staff_role(role: UserRole) -> bool:
    return role in STAFF_ROLES


def generate_temporary_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.get("/", response_model=List[RestaurantListResponse])
async def get_restaurants(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active_only: bool = Query(True),
    current_user = Depends(get_current_user_optional),
    db: "Prisma" = Depends(get_db_session),
):
    """Get list of restaurants (public endpoint)."""
    
    where_clause = {}
    if active_only:
        where_clause["isActive"] = True
    
    restaurants = await db.restaurant.find_many(
        where=where_clause,
        include={"address": True},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"}
    )
    
    return [RestaurantListResponse.model_validate(restaurant) for restaurant in restaurants]


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(
    restaurant_id: int,
    current_user = Depends(get_current_user_optional),
    db: "Prisma" = Depends(get_db_session),
):
    """Get restaurant by ID (public endpoint)."""
    
    restaurant = await db.restaurant.find_unique(
        where={"id": restaurant_id},
        include={"address": True}
    )
    
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    return RestaurantResponse.model_validate(restaurant)


@router.post("/", response_model=RestaurantResponse)
async def create_restaurant(
    restaurant_data: RestaurantCreate,
    current_user = Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Create a new restaurant (Admin only)."""
    
    try:
        # Create restaurant with address in a transaction
        result = await db.transaction([
            # Create restaurant
            db.restaurant.create(
                data={
                    "name": restaurant_data.name,
                    "description": restaurant_data.description,
                    "phone": restaurant_data.phone,
                    "email": restaurant_data.email,
                    "website": restaurant_data.website,
                    "operatingHours": restaurant_data.operatingHours,
                    "logo": restaurant_data.logo,
                    "coverImage": restaurant_data.coverImage,
                    "gallery": restaurant_data.gallery or [],
                    "isActive": restaurant_data.isActive
                }
            )
        ])
        
        restaurant = result[0]
        
        # Create address for the restaurant
        await db.address.create(
            data={
                "restaurantId": restaurant.id,
                "street": restaurant_data.street,
                "city": restaurant_data.city,
                "latitude": restaurant_data.latitude,
                "longitude": restaurant_data.longitude,
                "isDefault": True
            }
        )
        
        # Fetch restaurant with address
        restaurant_with_address = await db.restaurant.find_unique(
            where={"id": restaurant.id},
            include={"address": True}
        )
        
        return RestaurantResponse.model_validate(restaurant_with_address)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating restaurant: {str(e)}"
        )


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
async def update_restaurant(
    restaurant_id: int,
    restaurant_data: RestaurantUpdate,
    current_user = Depends(get_current_manager_or_admin),
    db: "Prisma" = Depends(get_db_session),
):
    """Update restaurant (Manager/Admin only). Managers can only update their own restaurant."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions - managers can only update their own restaurant
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own restaurant"
        )
    
    # Prepare update data
    update_data = {}
    for field, value in restaurant_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    try:
        updated_restaurant = await db.restaurant.update(
            where={"id": restaurant_id},
            data=update_data,
            include={"address": True}
        )
        
        return RestaurantResponse.model_validate(updated_restaurant)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating restaurant: {str(e)}"
        )


@router.delete("/{restaurant_id}")
async def delete_restaurant(
    restaurant_id: int,
    current_user = Depends(get_current_admin_user),
    db: "Prisma" = Depends(get_db_session),
):
    """Delete restaurant (Admin only)."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    try:
        await db.restaurant.delete(where={"id": restaurant_id})
        return {"message": "Restaurant deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting restaurant: {str(e)}"
        )


@router.patch("/{restaurant_id}/toggle-status")
async def toggle_restaurant_status(
    restaurant_id: int,
    current_user = Depends(get_current_manager_or_admin),
    db: "Prisma" = Depends(get_db_session),
):
    """Toggle restaurant active status (Manager/Admin only)."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own restaurant"
        )
    
    try:
        updated_restaurant = await db.restaurant.update(
            where={"id": restaurant_id},
            data={"isActive": not restaurant.isActive},
            include={"address": True}
        )
        
        return {
            "message": f"Restaurant {'activated' if updated_restaurant.isActive else 'deactivated'} successfully",
            "restaurant": RestaurantResponse.model_validate(updated_restaurant)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating restaurant status: {str(e)}"
        )


@router.get("/{restaurant_id}/staff", response_model=StaffListResponse)
async def get_restaurant_staff(
    restaurant_id: int,
    current_user = Depends(require_restaurant_staff),
    db: "Prisma" = Depends(get_db_session),
):
    """Get restaurant staff (Manager/Admin only). Managers can only see their own restaurant staff."""
    
    # Check if restaurant exists
    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    staff = await db.user.find_many(
        where={
            "restaurantId": restaurant_id,
            "role": {"in": ["WAITER", "CHEF", "MANAGER"]}
        },
        order={"role": "asc"}
    )
    
    return StaffListResponse(
        restaurantId=restaurant_id,
        restaurantName=restaurant.name,
        staff=[StaffResponse.model_validate(staff_user) for staff_user in staff],
        totalStaff=len(staff),
    )


@router.post("/{restaurant_id}/staff/invite", response_model=StaffInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_restaurant_staff(
    restaurant_id: int,
    staff_data: StaffInviteRequest,
    current_user = Depends(require_restaurant_staff),
    db: "Prisma" = Depends(get_db_session),
):
    """Create a staff user for a restaurant and send an invite SMS."""

    if not is_staff_role(staff_data.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be WAITER, CHEF, or MANAGER"
        )

    restaurant = await db.restaurant.find_unique(where={"id": restaurant_id})
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    duplicate_filters = [{"phone": staff_data.phone}]
    if staff_data.email:
        duplicate_filters.append({"email": staff_data.email})

    existing_user = await db.user.find_first(
        where={"OR": duplicate_filters}
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists"
        )

    temporary_password = generate_temporary_password()
    staff_user = await db.user.create(
        data={
            "email": staff_data.email,
            "phone": staff_data.phone,
            "firstName": staff_data.firstName,
            "lastName": staff_data.lastName,
            "password": get_password_hash(temporary_password),
            "role": staff_data.role.value,
            "restaurantId": restaurant_id,
            "isActive": True,
        }
    )

    active_sms_service = sms_service or SMSService()
    invite_message = (
        f"You have been invited to join {restaurant.name} as {staff_data.role.value}. "
        f"Temporary password: {temporary_password}. Use staff login to access Caravane."
    )
    sms_result = active_sms_service.send_sms(str(staff_data.phone), invite_message)

    if not sms_result.get("success", False):
        await db.user.delete(where={"id": staff_user.id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invite SMS"
        )

    return StaffInviteResponse(
        message="Staff user created and invite SMS sent",
        smsSent=True,
        staff=StaffResponse.model_validate(staff_user),
    )


@router.patch("/{restaurant_id}/staff/{user_id}", response_model=StaffResponse)
async def update_restaurant_staff(
    restaurant_id: int,
    user_id: int,
    staff_update: StaffUpdate,
    current_user = Depends(require_restaurant_staff),
    db: "Prisma" = Depends(get_db_session),
):
    """Update a staff user's role or active status."""

    if staff_update.role is not None and not is_staff_role(staff_update.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be WAITER, CHEF, or MANAGER"
        )

    staff_user = await db.user.find_unique(where={"id": user_id})
    if not staff_user or staff_user.restaurantId != restaurant_id or not is_staff_role(UserRole(staff_user.role)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff user not found"
        )

    update_data = {}
    if staff_update.role is not None:
        update_data["role"] = staff_update.role.value
    if staff_update.isActive is not None:
        update_data["isActive"] = staff_update.isActive

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )

    updated_user = await db.user.update(
        where={"id": user_id},
        data=update_data,
    )

    return StaffResponse.model_validate(updated_user)


@router.delete("/{restaurant_id}/staff/{user_id}")
async def deactivate_restaurant_staff(
    restaurant_id: int,
    user_id: int,
    current_user = Depends(require_restaurant_staff),
    db: "Prisma" = Depends(get_db_session),
):
    """Soft-delete staff by deactivating the account."""

    staff_user = await db.user.find_unique(where={"id": user_id})
    if not staff_user or staff_user.restaurantId != restaurant_id or not is_staff_role(UserRole(staff_user.role)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff user not found"
        )

    await db.user.update(
        where={"id": user_id},
        data={"isActive": False},
    )

    return {"message": "Staff user deactivated successfully"}
