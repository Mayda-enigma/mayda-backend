import enum
from datetime import datetime, timezone
from typing import Optional, List as TypingList

from sqlalchemy import (
    Column, Integer, BigInteger, Float, String, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index, JSON, Enum as SAEnum, ARRAY, Table
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# ── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    CLIENT = "CLIENT"
    WAITER = "WAITER"
    CHEF = "CHEF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class TableStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"


class ReservationStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class OrderType(str, enum.Enum):
    DINE_IN = "DINE_IN"
    TAKEAWAY = "TAKEAWAY"
    DELIVERY = "DELIVERY"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PromotionType(str, enum.Enum):
    DISCOUNT = "DISCOUNT"
    BOGO = "BOGO"
    FREE_DELIVERY = "FREE_DELIVERY"
    HAPPY_HOUR = "HAPPY_HOUR"
    SEASONAL = "SEASONAL"


class DiscountType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class InteractionType(str, enum.Enum):
    VIEW = "VIEW"
    LIKE = "LIKE"
    SHARE = "SHARE"
    ORDER = "ORDER"
    REVIEW = "REVIEW"
    SEARCH = "SEARCH"


class OtpPurpose(str, enum.Enum):
    STAFF_AUTH = "STAFF_AUTH"
    PAYMENT_CONFIRMATION = "PAYMENT_CONFIRMATION"
    PASSWORD_RESET = "PASSWORD_RESET"


# ── Models ───────────────────────────────────────────────────────────────────

class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id: int = Column(Integer, primary_key=True, default=1)
    currency: str = Column(String, nullable=False, server_default="USD")
    timezone: str = Column(String, nullable=False, server_default="UTC")
    defaultOperatingHours = Column(JSON, nullable=False, server_default=func.cast("{}", JSON))
    featureFlags = Column(JSON, nullable=False, server_default=func.cast("{}", JSON))
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)
    description: Optional[str] = Column(String, nullable=True)
    phone: str = Column(String, nullable=False)
    email: Optional[str] = Column(String, nullable=True)
    website: Optional[str] = Column(String, nullable=True)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    operatingHours = Column(JSON, nullable=False)
    logo: Optional[str] = Column(String, nullable=True)
    coverImage: Optional[str] = Column(String, nullable=True)
    gallery: TypingList[str] = Column(ARRAY(String), nullable=False, server_default="{}")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    address = relationship("Address", back_populates="restaurant", uselist=False, foreign_keys="Address.restaurantId")
    staff = relationship("User", back_populates="restaurant", foreign_keys="User.restaurantId")
    menus = relationship("Menu", back_populates="restaurant")
    tables = relationship("Table", back_populates="restaurant")
    orders = relationship("Order", back_populates="restaurant")
    reviews = relationship("Review", back_populates="restaurant")
    promotions = relationship("Promotion", back_populates="restaurant")
    inventory = relationship("Inventory", back_populates="restaurant")
    reservations = relationship("Reservation", back_populates="restaurant")
    loyaltyTransactions = relationship("LoyaltyTransaction", back_populates="restaurant")


class Address(Base):
    __tablename__ = "addresses"

    id: int = Column(Integer, primary_key=True)
    userId: Optional[int] = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=True)
    restaurantId: Optional[int] = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), unique=True, nullable=True)
    street: str = Column(String, nullable=False)
    city: str = Column(String, nullable=False)
    latitude: Optional[float] = Column(Float, nullable=True)
    longitude: Optional[float] = Column(Float, nullable=True)
    isDefault: bool = Column(Boolean, nullable=False, server_default="false")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="address", foreign_keys=[userId])
    restaurant = relationship("Restaurant", back_populates="address", foreign_keys=[restaurantId])
    orders = relationship("Order", back_populates="deliveryAddress", foreign_keys="Order.deliveryAddressId")


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True)
    email: Optional[str] = Column(String, unique=True, nullable=True)
    phone: int = Column(BigInteger, unique=True, nullable=False)
    firstName: str = Column(String, nullable=False)
    lastName: str = Column(String, nullable=False)
    role: UserRole = Column(SAEnum(UserRole), nullable=False, server_default="CLIENT")
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    password: str = Column(String, nullable=False)
    embeddedPref: Optional[str] = Column(String, nullable=True)
    specialinfo = Column(JSON, nullable=True)
    restaurantId: Optional[int] = Column(Integer, ForeignKey("restaurants.id"), nullable=True)

    restaurant = relationship("Restaurant", back_populates="staff", foreign_keys=[restaurantId])
    address = relationship("Address", back_populates="user", uselist=False, foreign_keys="Address.userId")
    refreshTokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    pushTokens = relationship("PushToken", back_populates="user", cascade="all, delete-orphan")
    tableSessions = relationship("TableSession", back_populates="waiter", foreign_keys="TableSession.waiterId", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", foreign_keys="Order.userId")
    reviews = relationship("Review", back_populates="user")
    loyaltyCard = relationship("LoyaltyCard", back_populates="user", uselist=False)
    reservations = relationship("Reservation", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    otpCodes = relationship("OtpCode", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: int = Column(Integer, primary_key=True)
    token: str = Column(String, unique=True, nullable=False)
    userId: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expiresAt: datetime = Column(DateTime(timezone=True), nullable=False)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    isRevoked: bool = Column(Boolean, nullable=False, server_default="false")

    user = relationship("User", back_populates="refreshTokens")


class PushToken(Base):
    __tablename__ = "push_tokens"

    id: int = Column(Integer, primary_key=True)
    userId: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: str = Column(String, unique=True, nullable=False)
    platform: str = Column(String, nullable=False)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="pushTokens")


class Menu(Base):
    __tablename__ = "menus"

    id: int = Column(Integer, primary_key=True)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name: str = Column(String, nullable=False)
    description: Optional[str] = Column(String, nullable=True)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    displayOrder: int = Column(Integer, nullable=False, server_default="0")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="menus")
    categories = relationship("MenuCategory", back_populates="menu", cascade="all, delete-orphan", order_by="MenuCategory.displayOrder")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: int = Column(Integer, primary_key=True)
    menuId: int = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    name: str = Column(String, nullable=False)
    description: Optional[str] = Column(String, nullable=True)
    image: Optional[str] = Column(String, nullable=True)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    displayOrder: int = Column(Integer, nullable=False, server_default="0")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    menu = relationship("Menu", back_populates="categories")
    dishes = relationship("Dish", back_populates="category", cascade="all, delete-orphan", order_by="Dish.displayOrder")


class Dish(Base):
    __tablename__ = "dishes"

    id: int = Column(Integer, primary_key=True)
    categoryId: int = Column(Integer, ForeignKey("menu_categories.id", ondelete="CASCADE"), nullable=False)
    name: str = Column(String, nullable=False)
    description: str = Column(String, nullable=False)
    price: float = Column(Float, nullable=False)
    image: Optional[str] = Column(String, nullable=True)
    gallery: TypingList[str] = Column(ARRAY(String), nullable=False, server_default="{}")
    isAvailable: bool = Column(Boolean, nullable=False, server_default="true")
    quantity: int = Column(Integer, nullable=False)
    preparationTime: int = Column(Integer, nullable=False)
    popularity: float = Column(Float, nullable=False, server_default="0")
    displayOrder: int = Column(Integer, nullable=False, server_default="0")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    category = relationship("MenuCategory", back_populates="dishes")
    ingredients = relationship("DishIngredient", back_populates="dish", cascade="all, delete-orphan")
    old_ingredient_links = relationship("DishInventoryLink", back_populates="dish")
    orderItems = relationship("OrderItem", back_populates="dish")
    reviews = relationship("Review", back_populates="dish")
    promotions = relationship("Promotion", secondary="promotion_dishes", back_populates="dishes")


class Table(Base):
    __tablename__ = "tables"

    id: int = Column(Integer, primary_key=True)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    number: str = Column(String, nullable=False)
    capacity: int = Column(Integer, nullable=False)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    status: TableStatus = Column(SAEnum(TableStatus), nullable=False, server_default="AVAILABLE")
    qrCode: Optional[str] = Column(String, nullable=True)
    nfcTag: Optional[str] = Column(String, nullable=True)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="tables")
    reservations = relationship("Reservation", back_populates="table")
    orders = relationship("Order", back_populates="table")
    sessions = relationship("TableSession", back_populates="table", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("restaurantId", "number", name="uq_tables_restaurant_number"),
    )


class TableSession(Base):
    __tablename__ = "table_sessions"

    id: int = Column(Integer, primary_key=True)
    tableId: int = Column(Integer, ForeignKey("tables.id", ondelete="CASCADE"), nullable=False)
    waiterId: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    startedAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    endedAt: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")

    table = relationship("Table", back_populates="sessions")
    waiter = relationship("User", back_populates="tableSessions", foreign_keys=[waiterId])

    __table_args__ = (
        Index("ix_table_sessions_table_active", "tableId", "isActive"),
        Index("ix_table_sessions_waiter_active", "waiterId", "isActive"),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: int = Column(Integer, primary_key=True)
    userId: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    tableId: Optional[int] = Column(Integer, ForeignKey("tables.id"), nullable=True)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    reservationStart: datetime = Column(DateTime(timezone=True), nullable=False)
    reservationEnd: datetime = Column(DateTime(timezone=True), nullable=False)
    status: ReservationStatus = Column(SAEnum(ReservationStatus), nullable=False, server_default="PENDING")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="reservations")
    table = relationship("Table", back_populates="reservations")
    restaurant = relationship("Restaurant", back_populates="reservations")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: int = Column(Integer, primary_key=True)
    orderId: int = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    dishId: int = Column(Integer, ForeignKey("dishes.id", ondelete="CASCADE"), nullable=False)
    quantity: int = Column(Integer, nullable=False)
    unitPrice: float = Column(Float, nullable=False)
    totalPrice: float = Column(Float, nullable=False)
    notes: Optional[str] = Column(String, nullable=True)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    order = relationship("Order", back_populates="items")
    dish = relationship("Dish", back_populates="orderItems")


class Order(Base):
    __tablename__ = "orders"

    id: int = Column(Integer, primary_key=True)
    orderNumber: str = Column(String, unique=True, nullable=False)
    userId: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    tableId: Optional[int] = Column(Integer, ForeignKey("tables.id"), nullable=True)
    type: OrderType = Column(SAEnum(OrderType), nullable=False, server_default="DINE_IN")
    status: OrderStatus = Column(SAEnum(OrderStatus), nullable=False, server_default="PENDING")
    subtotal: float = Column(Float, nullable=False)
    deliveryFee: float = Column(Float, nullable=False, server_default="0")
    discount: float = Column(Float, nullable=False, server_default="0")
    totalAmount: float = Column(Float, nullable=False)
    deliveryAddressId: Optional[int] = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    estimatedDeliveryTime: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    actualDeliveryTime: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    paymentStatus: PaymentStatus = Column(SAEnum(PaymentStatus), nullable=False, server_default="PENDING")
    paymentMethod: Optional[str] = Column(String, nullable=True)
    notes: Optional[str] = Column(String, nullable=True)
    orderTime: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    confirmedAt: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    preparedAt: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    readyAt: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    completedAt: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    paymentId: Optional[int] = Column(Integer, ForeignKey("payments.id"), nullable=True)

    user = relationship("User", back_populates="orders", foreign_keys=[userId])
    restaurant = relationship("Restaurant", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    deliveryAddress = relationship("Address", back_populates="orders", foreign_keys=[deliveryAddressId])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payments", back_populates="order", uselist=False, foreign_keys="Order.paymentId")
    loyaltyTransactions = relationship("LoyaltyTransaction", back_populates="order")


class Payments(Base):
    __tablename__ = "payments"

    id: int = Column(Integer, primary_key=True)
    paymentId: str = Column(String, unique=True, nullable=False)
    orderId: int = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    order = relationship("Order", back_populates="payment", foreign_keys="Payments.orderId")


class Notification(Base):
    __tablename__ = "notifications"

    id: int = Column(Integer, primary_key=True)
    userId: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    type: str = Column(String, nullable=False)
    title: str = Column(String, nullable=False)
    body: str = Column(String, nullable=False)
    metadata = Column(JSON, nullable=True)
    isRead: bool = Column(Boolean, nullable=False, server_default="false")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_read", "userId", "isRead"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: int = Column(Integer, primary_key=True)
    userId: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    dishId: Optional[int] = Column(Integer, ForeignKey("dishes.id"), nullable=True)
    rating: int = Column(Integer, nullable=False)
    comment: Optional[str] = Column(String, nullable=True)
    sentiment: Optional[str] = Column(String, nullable=True)
    sentimentScore: Optional[float] = Column(Float, nullable=True)
    isVerified: bool = Column(Boolean, nullable=False, server_default="false")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="reviews")
    restaurant = relationship("Restaurant", back_populates="reviews")
    dish = relationship("Dish", back_populates="reviews")


class LoyaltyCard(Base):
    __tablename__ = "loyalty_cards"

    id: int = Column(Integer, primary_key=True)
    userId: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    points: int = Column(Integer, nullable=False, server_default="0")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="loyaltyCard")
    transactions = relationship("LoyaltyTransaction", back_populates="loyaltyCard")


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id: int = Column(Integer, primary_key=True)
    loyaltyCardId: int = Column(Integer, ForeignKey("loyalty_cards.id"), nullable=False)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    points: int = Column(Integer, nullable=False)
    type: str = Column(String, nullable=False)
    description: str = Column(String, nullable=False)
    orderId: Optional[int] = Column(Integer, ForeignKey("orders.id"), nullable=True)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    loyaltyCard = relationship("LoyaltyCard", back_populates="transactions")
    restaurant = relationship("Restaurant", back_populates="loyaltyTransactions")
    order = relationship("Order", back_populates="loyaltyTransactions")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: int = Column(Integer, primary_key=True)
    userId: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code: str = Column(String, nullable=False)
    purpose: OtpPurpose = Column(SAEnum(OtpPurpose), nullable=False)
    isUsed: bool = Column(Boolean, nullable=False, server_default="false")
    expiresAt: datetime = Column(DateTime(timezone=True), nullable=False)
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="otpCodes")


# Association table for many-to-many relationship between promotions and dishes
promotion_dishes = Table(
    "promotion_dishes",
    Base.metadata,
    Column("promotionId", Integer, ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True),
    Column("dishId", Integer, ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True),
)


class Promotion(Base):
    __tablename__ = "promotions"

    id: int = Column(Integer, primary_key=True)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    title: str = Column(String, nullable=False)
    description: str = Column(String, nullable=False)
    image: Optional[str] = Column(String, nullable=True)
    type: PromotionType = Column(SAEnum(PromotionType), nullable=False)
    discountType: DiscountType = Column(SAEnum(DiscountType), nullable=False)
    discountValue: float = Column(Float, nullable=False)
    minOrderAmount: Optional[float] = Column(Float, nullable=True)
    startDate: datetime = Column(DateTime(timezone=True), nullable=False)
    endDate: datetime = Column(DateTime(timezone=True), nullable=False)
    maxUses: Optional[int] = Column(Integer, nullable=True)
    currentUses: int = Column(Integer, nullable=False, server_default="0")
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="promotions")
    dishes = relationship("Dish", secondary="promotion_dishes", back_populates="promotions")


class Inventory(Base):
    __tablename__ = "inventory"

    id: int = Column(Integer, primary_key=True)
    restaurantId: int = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name: str = Column(String, nullable=False)
    description: Optional[str] = Column(String, nullable=True)
    category: Optional[str] = Column(String, nullable=True)
    unit: str = Column(String, nullable=False)
    currentStock: float = Column(Float, nullable=False)
    minimumStock: float = Column(Float, nullable=False)
    unitPrice: float = Column(Float, nullable=False)
    supplier: Optional[str] = Column(String, nullable=True)
    location: Optional[str] = Column(String, nullable=True)
    expiryDate: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="inventory")
    old_ingredient_links = relationship("DishInventoryLink", back_populates="inventory")


class DishInventoryLink(Base):
    __tablename__ = "ingredient"

    id: int = Column(Integer, primary_key=True)
    dishId: int = Column(Integer, ForeignKey("dishes.id"), nullable=False)
    InventoryId: int = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    quantity: float = Column(Float, nullable=False)

    dish = relationship("Dish", back_populates="old_ingredient_links")
    inventory = relationship("Inventory", back_populates="old_ingredient_links")


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)
    description: Optional[str] = Column(String, nullable=True)
    allergenInfo: Optional[str] = Column(String, nullable=True)
    category: Optional[str] = Column(String, nullable=True)
    isVegetarian: bool = Column(Boolean, nullable=False, server_default="false")
    isVegan: bool = Column(Boolean, nullable=False, server_default="false")
    isGlutenFree: bool = Column(Boolean, nullable=False, server_default="false")
    isDairyFree: bool = Column(Boolean, nullable=False, server_default="false")
    nutritionalInfo = Column(JSON, nullable=True)
    isActive: bool = Column(Boolean, nullable=False, server_default="true")
    createdAt: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())

    dish_ingredients = relationship("DishIngredient", back_populates="ingredient")


class DishIngredient(Base):
    __tablename__ = "dish_ingredients"

    id: int = Column(Integer, primary_key=True)
    dishId: int = Column(Integer, ForeignKey("dishes.id", ondelete="CASCADE"), nullable=False)
    ingredientId: int = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity: Optional[float] = Column(Float, nullable=True)
    isOptional: bool = Column(Boolean, nullable=False, server_default="false")
    isVisible: bool = Column(Boolean, nullable=False, server_default="true")
    notes: Optional[str] = Column(String, nullable=True)

    dish = relationship("Dish", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="dish_ingredients")
