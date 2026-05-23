from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


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
    notes: str | None = None


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(BaseModel):
    id: int
    dishId: int
    quantity: int
    unitPrice: float
    totalPrice: float
    notes: str | None
    dish: dict  # Will contain dish details

    class Config:
        from_attributes = True


# Order Models
class OrderBase(BaseModel):
    restaurantId: int
    tableId: int | None = None  # None for takeaway/delivery
    type: OrderType = OrderType.DINE_IN
    notes: str | None = None
    # For delivery orders, if user has multiple addresses, they can specify which one
    deliveryAddressId: int | None = None  # Uses user's stored address by default


class OrderCreate(OrderBase):
    items: list[OrderItemCreate] = Field(..., min_items=1)
    # Note: No customer info needed - uses authenticated user's profile automatically


class DeliveryOrderCreate(BaseModel):
    """Special model for delivery orders that need address specification."""

    restaurantId: int
    items: list[OrderItemCreate] = Field(..., min_items=1)
    type: OrderType = OrderType.DELIVERY
    notes: str | None = None
    # For delivery, user can either use their stored address or provide a new one
    useStoredAddress: bool = True
    customDeliveryAddress: dict | None = None  # If useStoredAddress is False


class OrderUpdate(BaseModel):
    status: OrderStatus | None = None
    notes: str | None = None
    estimatedDeliveryTime: datetime | None = None
    paymentMethod: str | None = None


class OrderResponse(BaseModel):
    id: int
    orderNumber: str
    userId: int | None
    restaurantId: int
    tableId: int | None
    type: OrderType
    status: OrderStatus
    subtotal: float
    deliveryFee: float
    discount: float
    totalAmount: float
    deliveryAddressId: int | None
    estimatedDeliveryTime: datetime | None
    actualDeliveryTime: datetime | None
    paymentStatus: PaymentStatus
    paymentMethod: str | None
    notes: str | None
    orderTime: datetime
    confirmedAt: datetime | None
    preparedAt: datetime | None
    readyAt: datetime | None
    completedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime
    items: list[OrderItemResponse]
    user: dict | None = None
    table: dict | None = None
    restaurant: dict

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    id: int
    orderNumber: str
    restaurantId: int
    tableId: int | None
    type: OrderType
    status: OrderStatus
    totalAmount: float
    paymentStatus: PaymentStatus
    orderTime: datetime
    user: dict | None = None
    table: dict | None = None
    itemCount: int

    class Config:
        from_attributes = True


# Public Order Creation (for customers without auth)
class PublicOrderCreate(BaseModel):
    restaurantId: int
    tableId: int | None = None
    type: OrderType = OrderType.DINE_IN
    items: list[OrderItemCreate] = Field(..., min_items=1)
    notes: str | None = None
    # Customer info for non-authenticated orders
    customerName: str | None = None
    customerPhone: str | None = None
    deliveryAddressId: int | None = None


# Order Status Update for Staff
class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    notes: str | None = None
