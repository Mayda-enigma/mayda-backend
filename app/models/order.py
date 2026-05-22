from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    DINE_IN = "DINE_IN"
    TAKEAWAY = "TAKEAWAY"
    DELIVERY = "DELIVERY"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


# Order Item Models
class OrderItemBase(BaseModel):
    dishId: int
    quantity: int = Field(..., ge=1)
    notes: Optional[str] = None


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(BaseModel):
    id: int
    dishId: int
    quantity: int
    unitPrice: float
    totalPrice: float
    notes: Optional[str]
    dish: dict  # Will contain dish details
    
    class Config:
        from_attributes = True


# Order Models
class OrderBase(BaseModel):
    restaurantId: int
    tableId: Optional[int] = None  # None for takeaway/delivery
    type: OrderType = OrderType.DINE_IN
    notes: Optional[str] = None
    # For delivery orders, if user has multiple addresses, they can specify which one
    deliveryAddressId: Optional[int] = None  # Uses user's stored address by default


class OrderCreate(OrderBase):
    items: List[OrderItemCreate] = Field(..., min_items=1)
    # Note: No customer info needed - uses authenticated user's profile automatically


class DeliveryOrderCreate(BaseModel):
    """Special model for delivery orders that need address specification."""
    restaurantId: int
    items: List[OrderItemCreate] = Field(..., min_items=1)
    type: OrderType = OrderType.DELIVERY
    notes: Optional[str] = None
    # For delivery, user can either use their stored address or provide a new one
    useStoredAddress: bool = True
    customDeliveryAddress: Optional[dict] = None  # If useStoredAddress is False


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    notes: Optional[str] = None
    estimatedDeliveryTime: Optional[datetime] = None
    paymentMethod: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    orderNumber: str
    userId: Optional[int]
    restaurantId: int
    tableId: Optional[int]
    type: OrderType
    status: OrderStatus
    subtotal: float
    deliveryFee: float
    discount: float
    totalAmount: float
    deliveryAddressId: Optional[int]
    estimatedDeliveryTime: Optional[datetime]
    actualDeliveryTime: Optional[datetime]
    paymentStatus: PaymentStatus
    paymentMethod: Optional[str]
    notes: Optional[str]
    orderTime: datetime
    confirmedAt: Optional[datetime]
    preparedAt: Optional[datetime]
    readyAt: Optional[datetime]
    completedAt: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime
    items: List[OrderItemResponse]
    user: Optional[dict] = None
    table: Optional[dict] = None
    restaurant: dict
    
    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    id: int
    orderNumber: str
    restaurantId: int
    tableId: Optional[int]
    type: OrderType
    status: OrderStatus
    totalAmount: float
    paymentStatus: PaymentStatus
    orderTime: datetime
    user: Optional[dict] = None
    table: Optional[dict] = None
    itemCount: int
    
    class Config:
        from_attributes = True


# Public Order Creation (for customers without auth)
class PublicOrderCreate(BaseModel):
    restaurantId: int
    tableId: Optional[int] = None
    type: OrderType = OrderType.DINE_IN
    items: List[OrderItemCreate] = Field(..., min_items=1)
    notes: Optional[str] = None
    # Customer info for non-authenticated orders
    customerName: Optional[str] = None
    customerPhone: Optional[str] = None
    deliveryAddressId: Optional[int] = None


# Order Status Update for Staff
class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None
