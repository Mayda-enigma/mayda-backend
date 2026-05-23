from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.models.order import (
    OrderCreate, OrderResponse, OrderListResponse,
    PublicOrderCreate, OrderStatusUpdate, OrderStatus, OrderType, DeliveryOrderCreate
)
from app.core.database import get_db_session
from app.middleware.roles import (
    get_current_staff_user, get_current_user
)
from app.models.sqlalchemy_models import Order, OrderItem, User, Restaurant, Table, Dish, Address
from app.routes.notifications import create_restaurant_event_notifications


router = APIRouter(prefix="/orders", tags=["Orders"])


def _order_to_response_dict(order):
    """Convert SQLAlchemy order ORM to dict for OrderResponse validation."""
    order_dict = {c.name: getattr(order, c.name) for c in order.__table__.columns}

    order_dict["items"] = [
        {
            "id": item.id,
            "dishId": item.dishId,
            "quantity": item.quantity,
            "unitPrice": item.unitPrice,
            "totalPrice": item.totalPrice,
            "notes": item.notes,
            "dish": {
                "id": item.dish.id,
                "categoryId": item.dish.categoryId,
                "name": item.dish.name,
                "description": item.dish.description,
                "price": item.dish.price,
                "image": item.dish.image,
                "gallery": item.dish.gallery,
                "isAvailable": item.dish.isAvailable,
                "quantity": item.dish.quantity,
                "preparationTime": item.dish.preparationTime,
                "popularity": item.dish.popularity,
                "displayOrder": item.dish.displayOrder,
            }
        }
        for item in order.items
    ]

    if order.user:
        order_dict["user"] = {
            "id": order.user.id,
            "firstName": order.user.firstName,
            "lastName": order.user.lastName,
            "email": order.user.email,
            "phone": order.user.phone,
        }
    else:
        order_dict["user"] = None

    if order.table:
        order_dict["table"] = {
            "id": order.table.id,
            "number": order.table.number,
            "capacity": order.table.capacity,
        }
    else:
        order_dict["table"] = None

    if order.restaurant:
        order_dict["restaurant"] = {
            "id": order.restaurant.id,
            "name": order.restaurant.name,
            "description": order.restaurant.description,
            "phone": order.restaurant.phone,
            "email": order.restaurant.email,
            "website": order.restaurant.website,
            "logo": order.restaurant.logo,
            "coverImage": order.restaurant.coverImage,
            "isActive": order.restaurant.isActive,
        }

    return order_dict


# ==================== PUBLIC ORDER ENDPOINTS (No Auth Required) ====================

@router.post("/public", response_model=OrderResponse)
async def create_public_order(order_data: PublicOrderCreate, db: AsyncSession = Depends(get_db_session)):
    """
    Create order without authentication (for walk-in customers using QR codes/NFC at tables).
    
    Security restrictions:
    - Only DINE_IN orders allowed (no delivery/takeaway without authentication)
    - Must specify a valid tableId
    - Order amounts limited to prevent abuse
    """
    
    # Security restriction: Only DINE_IN orders allowed for public endpoint
    if order_data.type != OrderType.DINE_IN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only dine-in orders are allowed without authentication. Please register/login for delivery or takeaway orders."
        )
    
    # Security restriction: Must specify a table for public orders
    if not order_data.tableId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table ID is required for public orders"
        )
    
    # Validate restaurant exists
    result = await db.execute(select(Restaurant).where(Restaurant.id == order_data.restaurantId))
    restaurant = result.scalar_one_or_none()
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Validate table if provided
    if order_data.tableId:
        result = await db.execute(
            select(Table).where(and_(Table.id == order_data.tableId, Table.restaurantId == order_data.restaurantId))
        )
        table = result.scalar_one_or_none()
        if not table or not table.isActive:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found or inactive"
            )
    
    # Validate dishes and calculate totals
    if not order_data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item"
        )
    
    subtotal = 0
    validated_items = []
    
    for item in order_data.items:
        # Get dish details
        result = await db.execute(select(Dish).where(Dish.id == item.dishId))
        dish = result.scalar_one_or_none()
        if not dish:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dish with ID {item.dishId} not found"
            )
        
        if not dish.isAvailable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dish '{dish.name}' is not available"
            )
        
        if dish.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough quantity for dish '{dish.name}'. Available: {dish.quantity}, Requested: {item.quantity}"
            )
        
        # Calculate item total
        item_total = dish.price * item.quantity
        subtotal += item_total
        
        validated_items.append({
            "dish": dish,
            "quantity": item.quantity,
            "unitPrice": dish.price,
            "totalPrice": item_total,
            "notes": item.notes
        })
    
    # Calculate delivery fee (simple logic)
    delivery_fee = 0
    if order_data.type == OrderType.DELIVERY:
        delivery_fee = 50.0  # Fixed delivery fee for now
    
    # Calculate total
    discount = 0  # No discount logic for now
    total_amount = subtotal + delivery_fee - discount
    
    # Security restriction: Limit order amount for public orders to prevent abuse
    MAX_PUBLIC_ORDER_AMOUNT = 1000.0  # Adjust based on your restaurant's typical order size
    if total_amount > MAX_PUBLIC_ORDER_AMOUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order amount ({total_amount}) exceeds maximum allowed for public orders ({MAX_PUBLIC_ORDER_AMOUNT}). Please register/login for larger orders."
        )
    
    # Generate order number
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    try:
        # Create order
        order = Order(
            orderNumber=order_number,
            restaurantId=order_data.restaurantId,
            tableId=order_data.tableId,
            type=order_data.type.value,
            status=OrderStatus.PENDING.value,
            subtotal=subtotal,
            deliveryFee=delivery_fee,
            discount=discount,
            totalAmount=total_amount,
            deliveryAddressId=order_data.deliveryAddressId,
            paymentStatus="PENDING",
            notes=order_data.notes,
            orderTime=datetime.now()
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        
        # Create order items and update dish quantities
        for item_data in validated_items:
            order_item = OrderItem(
                orderId=order.id,
                dishId=item_data["dish"].id,
                quantity=item_data["quantity"],
                unitPrice=item_data["unitPrice"],
                totalPrice=item_data["totalPrice"],
                notes=item_data["notes"]
            )
            db.add(order_item)
            
            # Update dish quantity
            item_data["dish"].quantity = item_data["dish"].quantity - item_data["quantity"]
        
        await db.commit()
        
        # Fetch complete order with relations
        result = await db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.dish),
                selectinload(Order.table),
                selectinload(Order.restaurant),
                selectinload(Order.user),
            )
        )
        complete_order = result.scalar_one()

        await create_restaurant_event_notifications(
            db=db,
            restaurant_id=order.restaurantId,
            notification_type="order_placed",
            title="New order placed",
            body=f"Order {order.orderNumber} was placed for {restaurant.name}.",
            metadata={
                "orderId": order.id,
                "orderNumber": order.orderNumber,
                "restaurantId": order.restaurantId,
                "totalAmount": total_amount,
            },
        )
        
        return OrderResponse.model_validate(_order_to_response_dict(complete_order))
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating order: {str(e)}"
        )


# ==================== AUTHENTICATED ORDER ENDPOINTS ====================

@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create order for authenticated user using their stored profile information."""
    
    # Get user's complete profile including address
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(selectinload(User.address))
    )
    user_profile = result.scalar_one_or_none()
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # For delivery orders, ensure user has an address
    if order_data.type == OrderType.DELIVERY:
        if not order_data.deliveryAddressId and not user_profile.address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery address is required. Please add an address to your profile or specify a delivery address."
            )
        
        # Use user's default address if no specific address provided
        if not order_data.deliveryAddressId and user_profile.address:
            order_data.deliveryAddressId = user_profile.address.id
    
    # Validate restaurant
    result = await db.execute(select(Restaurant).where(Restaurant.id == order_data.restaurantId))
    restaurant = result.scalar_one_or_none()
    if not restaurant or not restaurant.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found or inactive"
        )
    
    # Validate table if provided
    if order_data.tableId:
        result = await db.execute(
            select(Table).where(and_(Table.id == order_data.tableId, Table.restaurantId == order_data.restaurantId))
        )
        table = result.scalar_one_or_none()
        if not table or not table.isActive:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found or inactive"
            )
    
    # [Same validation logic as public order...]
    # Validate dishes and calculate totals
    if not order_data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item"
        )
    
    subtotal = 0
    validated_items = []
    
    for item in order_data.items:
        result = await db.execute(select(Dish).where(Dish.id == item.dishId))
        dish = result.scalar_one_or_none()
        if not dish:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dish with ID {item.dishId} not found"
            )
        
        if not dish.isAvailable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dish '{dish.name}' is not available"
            )
        
        if dish.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough quantity for dish '{dish.name}'. Available: {dish.quantity}, Requested: {item.quantity}"
            )
        
        item_total = dish.price * item.quantity
        subtotal += item_total
        
        validated_items.append({
            "dish": dish,
            "quantity": item.quantity,
            "unitPrice": dish.price,
            "totalPrice": item_total,
            "notes": item.notes
        })
    
    delivery_fee = 50.0 if order_data.type == OrderType.DELIVERY else 0
    discount = 0
    total_amount = subtotal + delivery_fee - discount
    
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    try:
        order = Order(
            orderNumber=order_number,
            userId=current_user.id,
            restaurantId=order_data.restaurantId,
            tableId=order_data.tableId,
            type=order_data.type.value,
            status=OrderStatus.PENDING.value,
            subtotal=subtotal,
            deliveryFee=delivery_fee,
            discount=discount,
            totalAmount=total_amount,
            deliveryAddressId=order_data.deliveryAddressId,
            paymentStatus="PENDING",
            notes=order_data.notes,
            orderTime=datetime.now()
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        
        # Create order items and update quantities
        for item_data in validated_items:
            order_item = OrderItem(
                orderId=order.id,
                dishId=item_data["dish"].id,
                quantity=item_data["quantity"],
                unitPrice=item_data["unitPrice"],
                totalPrice=item_data["totalPrice"],
                notes=item_data["notes"]
            )
            db.add(order_item)
            
            item_data["dish"].quantity = item_data["dish"].quantity - item_data["quantity"]
        
        await db.commit()
        
        # Fetch complete order with user contact details
        result = await db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.dish),
                selectinload(Order.table),
                selectinload(Order.restaurant),
                selectinload(Order.deliveryAddress),
                selectinload(Order.user),
            )
        )
        complete_order = result.scalar_one()

        await create_restaurant_event_notifications(
            db=db,
            restaurant_id=order.restaurantId,
            notification_type="order_placed",
            title="New order placed",
            body=f"Order {order.orderNumber} was placed for {restaurant.name}.",
            metadata={
                "orderId": order.id,
                "orderNumber": order.orderNumber,
                "restaurantId": order.restaurantId,
                "userId": current_user.id,
                "totalAmount": total_amount,
            },
        )
        
        return OrderResponse.model_validate(_order_to_response_dict(complete_order))
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating order: {str(e)}"
        )


@router.post("/delivery", response_model=OrderResponse)
async def create_delivery_order(
    order_data: DeliveryOrderCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create delivery order for authenticated user with automatic address handling."""
    
    # Get user's complete profile including address
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(selectinload(User.address))
    )
    user_profile = result.scalar_one_or_none()
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Ensure user has required contact information
    if not user_profile.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required for delivery orders. Please update your profile."
        )
    
    delivery_address_id = None
    
    if order_data.useStoredAddress:
        # Use user's stored address
        if not user_profile.address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No stored address found. Please add an address to your profile or provide a custom delivery address."
            )
        delivery_address_id = user_profile.address.id
    else:
        # Create new address from custom delivery address
        if not order_data.customDeliveryAddress:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom delivery address is required when not using stored address"
            )
        
        # Create temporary address for this delivery
        new_address = Address(
            street=order_data.customDeliveryAddress.get("street"),
            city=order_data.customDeliveryAddress.get("city"),
            latitude=order_data.customDeliveryAddress.get("latitude"),
            longitude=order_data.customDeliveryAddress.get("longitude"),
            isDefault=False
        )
        db.add(new_address)
        await db.commit()
        await db.refresh(new_address)
        delivery_address_id = new_address.id
    
    # Convert to standard OrderCreate for processing
    standard_order = OrderCreate(
        restaurantId=order_data.restaurantId,
        tableId=None,  # No table for delivery
        type=OrderType.DELIVERY,
        items=order_data.items,
        notes=order_data.notes,
        deliveryAddressId=delivery_address_id
    )
    
    # Use the standard order creation logic
    return await create_order(standard_order, current_user)


@router.get("/my-orders", response_model=List[OrderListResponse])
async def get_my_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get current user's orders."""
    
    result = await db.execute(
        select(Order)
        .where(Order.userId == current_user.id)
        .options(
            selectinload(Order.table),
            selectinload(Order.restaurant),
            selectinload(Order.items),
            selectinload(Order.deliveryAddress),
            selectinload(Order.user),
        )
        .offset(skip)
        .limit(limit)
        .order_by(Order.orderTime.desc())
    )
    orders = result.scalars().all()
    
    # Add item count to each order
    order_list = []
    for order in orders:
        order_dict = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        order_dict["itemCount"] = len(order.items)
        
        # Convert user object to dict if it exists
        if order.user:
            order_dict["user"] = {
                "id": order.user.id,
                "firstName": order.user.firstName,
                "lastName": order.user.lastName,
                "email": order.user.email,
                "phone": order.user.phone
            }
        else:
            order_dict["user"] = None
            
        # Convert table object to dict if it exists
        if order.table:
            order_dict["table"] = {
                "id": order.table.id,
                "number": order.table.number,
                "capacity": order.table.capacity
            }
        else:
            order_dict["table"] = None
            
        order_list.append(OrderListResponse.model_validate(order_dict))
    
    return order_list


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get order by ID. Users can only see their own orders, staff can see restaurant orders."""
    
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.dish),
            selectinload(Order.table),
            selectinload(Order.restaurant),
            selectinload(Order.user),
        )
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Check permissions
    if current_user.role in ["ADMIN"]:
        # Admin can see all orders
        pass
    elif current_user.role in ["WAITER", "CHEF", "MANAGER"]:
        # Staff can see orders from their restaurant
        if current_user.restaurantId != order.restaurantId:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view orders from your restaurant"
            )
    else:
        # Regular users can only see their own orders
        if order.userId != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own orders"
            )
    
    return OrderResponse.model_validate(_order_to_response_dict(order))


@router.get("/public/status/{order_number}", response_model=OrderResponse)
async def get_public_order_status(order_number: str, db: AsyncSession = Depends(get_db_session)):
    """
    Get order status by order number (Public endpoint for QR code orders).
    
    This allows customers who placed orders via QR codes to check their order status
    without authentication by using the order number they received.
    """
    
    result = await db.execute(
        select(Order)
        .where(Order.orderNumber == order_number)
        .options(
            selectinload(Order.items).selectinload(OrderItem.dish),
            selectinload(Order.table),
            selectinload(Order.restaurant),
            selectinload(Order.user),
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Only show public orders (no user associated) or limit information
    if order.userId is not None:
        # This is an authenticated user's order, don't expose via public endpoint
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return OrderResponse.model_validate(_order_to_response_dict(order))


# ==================== STAFF ORDER MANAGEMENT ====================

@router.get("/restaurant/{restaurant_id}", response_model=List[OrderListResponse])
async def get_restaurant_orders(
    restaurant_id: int,
    status: Optional[OrderStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get orders for a restaurant (Staff only)."""
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view orders from your own restaurant"
        )
    
    query = select(Order).where(Order.restaurantId == restaurant_id)
    if status:
        query = query.where(Order.status == status.value)
    
    query = query.options(
        selectinload(Order.table),
        selectinload(Order.restaurant),
        selectinload(Order.items),
        selectinload(Order.user),
    ).offset(skip).limit(limit).order_by(Order.orderTime.desc())
    
    result = await db.execute(query)
    orders = result.scalars().all()

    # Add item count
    order_list = []
    for order in orders:
        order_dict = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        order_dict["itemCount"] = len(order.items)

        # Convert user object to dict if it exists
        if order.user:
            order_dict["user"] = {
                "id": order.user.id,
                "firstName": order.user.firstName,
                "lastName": order.user.lastName,
                "phone": order.user.phone
            }
        else:
            order_dict["user"] = None
            
        # Convert table object to dict if it exists
        if order.table:
            order_dict["table"] = {
                "id": order.table.id,
                "number": order.table.number,
                "capacity": order.table.capacity
            }
        else:
            order_dict["table"] = None
            
        order_list.append(OrderListResponse.model_validate(order_dict))
    
    return order_list


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update order status (Staff only)."""
    
    # Check if order exists
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != order.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update orders from your own restaurant"
        )
    
    # Prepare update data
    order.status = status_update.status.value
    order.updatedAt = datetime.now()
    
    if status_update.notes:
        order.notes = status_update.notes
    
    # Set timestamp fields based on status
    if status_update.status == OrderStatus.CONFIRMED:
        order.confirmedAt = datetime.now()
    elif status_update.status == OrderStatus.PREPARING:
        order.preparedAt = datetime.now()
    elif status_update.status == OrderStatus.READY:
        order.readyAt = datetime.now()
    elif status_update.status == OrderStatus.COMPLETED:
        order.completedAt = datetime.now()
    
    try:
        await db.commit()
        
        # Re-fetch with eager loaded relations
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.dish),
                selectinload(Order.table),
                selectinload(Order.restaurant),
                selectinload(Order.user),
            )
        )
        updated_order = result.scalar_one()

        return OrderResponse.model_validate(_order_to_response_dict(updated_order))
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating order status: {str(e)}"
        )


@router.get("/table/{table_id}/current", response_model=List[OrderListResponse])
async def get_table_current_orders(
    table_id: int,
    current_user = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get current orders for a specific table (Staff only)."""
    
    # Check if table exists
    result = await db.execute(select(Table).where(Table.id == table_id))
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check permissions
    if current_user.role != "ADMIN" and current_user.restaurantId != table.restaurantId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view orders from your own restaurant"
        )
    
    # Get current orders for this table
    result = await db.execute(
        select(Order)
        .where(and_(
            Order.tableId == table_id,
            Order.status.in_(["PENDING", "CONFIRMED", "PREPARING", "READY"])
        ))
        .options(
            selectinload(Order.table),
            selectinload(Order.restaurant),
            selectinload(Order.items),
            selectinload(Order.user),
        )
        .order_by(Order.orderTime.desc())
    )
    orders = result.scalars().all()
    
    # Add item count
    order_list = []
    for order in orders:
        order_dict = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        order_dict["itemCount"] = len(order.items)
        
        # Convert user object to dict if it exists
        if order.user:
            order_dict["user"] = {
                "id": order.user.id,
                "firstName": order.user.firstName,
                "lastName": order.user.lastName,
                "phone": order.user.phone
            }
        else:
            order_dict["user"] = None
            
        # Convert table object to dict if it exists
        if order.table:
            order_dict["table"] = {
                "id": order.table.id,
                "number": order.table.number,
                "capacity": order.table.capacity
            }
        else:
            order_dict["table"] = None
            
        order_list.append(OrderListResponse.model_validate(order_dict))
    
    return order_list
