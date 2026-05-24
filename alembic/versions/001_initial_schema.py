"""Initial database schema.

Revision ID: fb6a4e84bc72
Revises:
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fb6a4e84bc72"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE \"UserRole\" AS ENUM ('CLIENT', 'WAITER', 'CHEF', 'MANAGER', 'ADMIN')")
    op.execute("CREATE TYPE \"TableStatus\" AS ENUM ('AVAILABLE', 'OCCUPIED')")
    op.execute(
        "CREATE TYPE \"ReservationStatus\" AS ENUM ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')"
    )
    op.execute("CREATE TYPE \"OrderType\" AS ENUM ('DINE_IN', 'TAKEAWAY', 'DELIVERY')")
    op.execute(
        "CREATE TYPE \"OrderStatus\" AS ENUM ('PENDING', 'CONFIRMED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'COMPLETED', 'CANCELLED')"
    )
    op.execute("CREATE TYPE \"PaymentStatus\" AS ENUM ('PENDING', 'PAID', 'FAILED', 'REFUNDED')")
    op.execute("CREATE TYPE \"PromotionType\" AS ENUM ('DISCOUNT', 'BOGO', 'FREE_DELIVERY', 'HAPPY_HOUR', 'SEASONAL')")
    op.execute("CREATE TYPE \"DiscountType\" AS ENUM ('PERCENTAGE', 'FIXED_AMOUNT')")
    op.execute("CREATE TYPE \"InteractionType\" AS ENUM ('VIEW', 'LIKE', 'SHARE', 'ORDER', 'REVIEW', 'SEARCH')")
    op.execute("CREATE TYPE \"OtpPurpose\" AS ENUM ('STAFF_AUTH', 'PAYMENT_CONFIRMATION', 'PASSWORD_RESET')")

    # ── Tables (ordered by dependency: parents before children) ─────────────

    # 1. restaurants (no FKs)
    op.create_table(
        "restaurants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("operatingHours", postgresql.JSONB(), nullable=False),
        sa.Column("logo", sa.Text(), nullable=True),
        sa.Column("coverImage", sa.Text(), nullable=True),
        sa.Column(
            "gallery",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. users (FK: restaurantId → restaurants.id)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.BigInteger(), nullable=False),
        sa.Column("firstName", sa.Text(), nullable=False),
        sa.Column("lastName", sa.Text(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "CLIENT",
                "WAITER",
                "CHEF",
                "MANAGER",
                "ADMIN",
                name="UserRole",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'CLIENT'"),
        ),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("password", sa.Text(), nullable=False),
        sa.Column("embeddedPref", sa.Text(), nullable=True),
        sa.Column("specialinfo", postgresql.JSONB(), nullable=True),
        sa.Column("restaurantId", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
    )
    op.create_foreign_key(
        "users_restaurantId_fkey",
        "users",
        "restaurants",
        ["restaurantId"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. refresh_tokens (FK: userId → users.id)
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("isRevoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_foreign_key(
        "refresh_tokens_userId_fkey",
        "refresh_tokens",
        "users",
        ["userId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 4. push_tokens (FK: userId → users.id)
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_foreign_key(
        "push_tokens_userId_fkey",
        "push_tokens",
        "users",
        ["userId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 5. addresses (FK: userId → users.id, restaurantId → restaurants.id)
    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=True),
        sa.Column("restaurantId", sa.Integer(), nullable=True),
        sa.Column("street", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("isDefault", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("userId"),
        sa.UniqueConstraint("restaurantId"),
    )
    op.create_foreign_key(
        "addresses_userId_fkey",
        "addresses",
        "users",
        ["userId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "addresses_restaurantId_fkey",
        "addresses",
        "restaurants",
        ["restaurantId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 6. tables (FK: restaurantId → restaurants.id)
    op.create_table(
        "tables",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "status",
            postgresql.ENUM("AVAILABLE", "OCCUPIED", name="TableStatus", create_type=False),
            nullable=False,
            server_default=sa.text("'AVAILABLE'"),
        ),
        sa.Column("qrCode", sa.Text(), nullable=True),
        sa.Column("nfcTag", sa.Text(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("restaurantId", "number"),
    )
    op.create_foreign_key(
        "tables_restaurantId_fkey",
        "tables",
        "restaurants",
        ["restaurantId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 7. table_sessions (FK: tableId → tables.id, waiterId → users.id)
    op.create_table(
        "table_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tableId", sa.Integer(), nullable=False),
        sa.Column("waiterId", sa.Integer(), nullable=False),
        sa.Column(
            "startedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("endedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "table_sessions_tableId_fkey",
        "table_sessions",
        "tables",
        ["tableId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "table_sessions_waiterId_fkey",
        "table_sessions",
        "users",
        ["waiterId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_table_sessions_table_active", "table_sessions", ["tableId", "isActive"])
    op.create_index("ix_table_sessions_waiter_active", "table_sessions", ["waiterId", "isActive"])

    # 8. menus (FK: restaurantId → restaurants.id)
    op.create_table(
        "menus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("displayOrder", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "menus_restaurantId_fkey",
        "menus",
        "restaurants",
        ["restaurantId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 9. menu_categories (FK: menuId → menus.id)
    op.create_table(
        "menu_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("menuId", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("displayOrder", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "menu_categories_menuId_fkey",
        "menu_categories",
        "menus",
        ["menuId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 10. dishes (FK: categoryId → menu_categories.id)
    op.create_table(
        "dishes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("categoryId", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column(
            "gallery",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("isAvailable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("preparationTime", sa.Integer(), nullable=False),
        sa.Column("popularity", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("displayOrder", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "dishes_categoryId_fkey",
        "dishes",
        "menu_categories",
        ["categoryId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 11. reservations (FK: userId → users.id, tableId → tables.id, restaurantId → restaurants.id)
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("tableId", sa.Integer(), nullable=True),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("reservationStart", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reservationEnd", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "CONFIRMED",
                "CANCELLED",
                "COMPLETED",
                "NO_SHOW",
                name="ReservationStatus",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key("reservations_userId_fkey", "reservations", "users", ["userId"], ["id"])
    op.create_foreign_key(
        "reservations_tableId_fkey",
        "reservations",
        "tables",
        ["tableId"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "reservations_restaurantId_fkey",
        "reservations",
        "restaurants",
        ["restaurantId"],
        ["id"],
    )

    # 12. orders (FK: userId → users.id, restaurantId → restaurants.id, tableId → tables.id, deliveryAddressId → addresses.id)
    #     paymentId FK added after payments table is created
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("orderNumber", sa.Text(), nullable=False),
        sa.Column("userId", sa.Integer(), nullable=True),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("tableId", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM("DINE_IN", "TAKEAWAY", "DELIVERY", name="OrderType", create_type=False),
            nullable=False,
            server_default=sa.text("'DINE_IN'"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "CONFIRMED",
                "PREPARING",
                "READY",
                "OUT_FOR_DELIVERY",
                "COMPLETED",
                "CANCELLED",
                name="OrderStatus",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("subtotal", sa.Float(), nullable=False),
        sa.Column("deliveryFee", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("discount", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("totalAmount", sa.Float(), nullable=False),
        sa.Column("deliveryAddressId", sa.Integer(), nullable=True),
        sa.Column("estimatedDeliveryTime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualDeliveryTime", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "paymentStatus",
            postgresql.ENUM(
                "PENDING",
                "PAID",
                "FAILED",
                "REFUNDED",
                name="PaymentStatus",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("paymentMethod", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "orderTime",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("confirmedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preparedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("readyAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("paymentId", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orderNumber"),
    )
    op.create_foreign_key("orders_userId_fkey", "orders", "users", ["userId"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("orders_restaurantId_fkey", "orders", "restaurants", ["restaurantId"], ["id"])
    op.create_foreign_key(
        "orders_tableId_fkey",
        "orders",
        "tables",
        ["tableId"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "orders_deliveryAddressId_fkey",
        "orders",
        "addresses",
        ["deliveryAddressId"],
        ["id"],
        ondelete="SET NULL",
    )

    # 13. order_items (FK: orderId → orders.id, dishId → dishes.id)
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("orderId", sa.Integer(), nullable=False),
        sa.Column("dishId", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unitPrice", sa.Float(), nullable=False),
        sa.Column("totalPrice", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "order_items_orderId_fkey",
        "order_items",
        "orders",
        ["orderId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key("order_items_dishId_fkey", "order_items", "dishes", ["dishId"], ["id"])

    # 14. payments (FK: orderId → orders.id) — then backlink orders.paymentId → payments.id
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("paymentId", sa.Text(), nullable=False),
        sa.Column("orderId", sa.Integer(), nullable=False),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paymentId"),
        sa.UniqueConstraint("orderId"),
    )
    op.create_foreign_key(
        "payments_orderId_fkey",
        "payments",
        "orders",
        ["orderId"],
        ["id"],
        ondelete="CASCADE",
    )
    # Backlink FK order.paymentId → payments.id (circular, added after both tables exist)
    op.create_foreign_key(
        "orders_paymentId_fkey",
        "orders",
        "payments",
        ["paymentId"],
        ["id"],
        ondelete="SET NULL",
    )

    # 15. loyalty_cards (FK: userId → users.id)
    op.create_table(
        "loyalty_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("userId"),
    )
    op.create_foreign_key(
        "loyalty_cards_userId_fkey",
        "loyalty_cards",
        "users",
        ["userId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 16. loyalty_transactions (FK: loyaltyCardId → loyalty_cards.id, restaurantId → restaurants.id)
    op.create_table(
        "loyalty_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("loyaltyCardId", sa.Integer(), nullable=False),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "loyalty_transactions_loyaltyCardId_fkey",
        "loyalty_transactions",
        "loyalty_cards",
        ["loyaltyCardId"],
        ["id"],
    )
    op.create_foreign_key(
        "loyalty_transactions_restaurantId_fkey",
        "loyalty_transactions",
        "restaurants",
        ["restaurantId"],
        ["id"],
    )

    # 17. reviews (FK: userId → users.id, restaurantId → restaurants.id, dishId → dishes.id)
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("dishId", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.Text(), nullable=True),
        sa.Column("sentimentScore", sa.Float(), nullable=True),
        sa.Column("isVerified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key("reviews_userId_fkey", "reviews", "users", ["userId"], ["id"])
    op.create_foreign_key("reviews_restaurantId_fkey", "reviews", "restaurants", ["restaurantId"], ["id"])
    op.create_foreign_key(
        "reviews_dishId_fkey",
        "reviews",
        "dishes",
        ["dishId"],
        ["id"],
        ondelete="SET NULL",
    )

    # 18. promotions (FK: restaurantId → restaurants.id)
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(
                "DISCOUNT",
                "BOGO",
                "FREE_DELIVERY",
                "HAPPY_HOUR",
                "SEASONAL",
                name="PromotionType",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "discountType",
            postgresql.ENUM("PERCENTAGE", "FIXED_AMOUNT", name="DiscountType", create_type=False),
            nullable=False,
        ),
        sa.Column("discountValue", sa.Float(), nullable=False),
        sa.Column("minOrderAmount", sa.Float(), nullable=True),
        sa.Column("startDate", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endDate", sa.DateTime(timezone=True), nullable=False),
        sa.Column("maxUses", sa.Integer(), nullable=True),
        sa.Column("currentUses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "promotions_restaurantId_fkey",
        "promotions",
        "restaurants",
        ["restaurantId"],
        ["id"],
    )

    # 19. promotion_dishes (FK: promotionId → promotions.id, dishId → dishes.id)
    op.create_table(
        "promotion_dishes",
        sa.Column("promotionId", sa.Integer(), nullable=False),
        sa.Column("dishId", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("promotionId", "dishId"),
    )
    op.create_foreign_key(
        "promotion_dishes_promotionId_fkey",
        "promotion_dishes",
        "promotions",
        ["promotionId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "promotion_dishes_dishId_fkey",
        "promotion_dishes",
        "dishes",
        ["dishId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 20. inventory (FK: restaurantId → restaurants.id)
    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restaurantId", sa.Integer(), nullable=False),
        sa.Column("itemName", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("currentStock", sa.Float(), nullable=False),
        sa.Column("minStock", sa.Float(), nullable=False),
        sa.Column("maxStock", sa.Float(), nullable=True),
        sa.Column("unitCost", sa.Float(), nullable=True),
        sa.Column("supplier", sa.Text(), nullable=True),
        sa.Column("supplierContact", sa.Text(), nullable=True),
        sa.Column("lastRestocked", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("restaurantId", "itemName"),
    )
    op.create_foreign_key(
        "inventory_restaurantId_fkey",
        "inventory",
        "restaurants",
        ["restaurantId"],
        ["id"],
    )

    # 21. ingredient (FK: dishId → dishes.id, InventoryId → inventory.id)
    op.create_table(
        "ingredient",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dishId", sa.Integer(), nullable=False),
        sa.Column("InventoryId", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key("ingredient_dishId_fkey", "ingredient", "dishes", ["dishId"], ["id"])
    op.create_foreign_key(
        "ingredient_InventoryId_fkey",
        "ingredient",
        "inventory",
        ["InventoryId"],
        ["id"],
    )

    # 22. notifications (FK: userId → users.id)
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("isRead", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key("notifications_userId_fkey", "notifications", "users", ["userId"], ["id"])
    op.create_index("ix_notifications_user_read", "notifications", ["userId", "isRead"])

    # 23. otp_codes (FK: userId → users.id)
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "purpose",
            postgresql.ENUM(
                "STAFF_AUTH",
                "PAYMENT_CONFIRMATION",
                "PASSWORD_RESET",
                name="OtpPurpose",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("isUsed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "otp_codes_userId_fkey",
        "otp_codes",
        "users",
        ["userId"],
        ["id"],
        ondelete="CASCADE",
    )

    # 24. platform_settings (no FKs)
    op.create_table(
        "platform_settings",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=False,
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("currency", sa.Text(), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("timezone", sa.Text(), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column(
            "defaultOperatingHours",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "featureFlags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
    op.drop_table("otp_codes")
    op.drop_table("notifications")
    op.drop_table("ingredient")
    op.drop_table("inventory")
    op.drop_table("promotion_dishes")
    op.drop_table("promotions")
    op.drop_table("reviews")
    op.drop_table("loyalty_transactions")
    op.drop_table("loyalty_cards")
    op.drop_table("payments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("reservations")
    op.drop_table("dishes")
    op.drop_table("menu_categories")
    op.drop_table("menus")
    op.drop_table("table_sessions")
    op.drop_table("tables")
    op.drop_table("addresses")
    op.drop_table("push_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("restaurants")
    op.execute('DROP TYPE IF EXISTS "OtpPurpose"')
    op.execute('DROP TYPE IF EXISTS "InteractionType"')
    op.execute('DROP TYPE IF EXISTS "DiscountType"')
    op.execute('DROP TYPE IF EXISTS "PromotionType"')
    op.execute('DROP TYPE IF EXISTS "PaymentStatus"')
    op.execute('DROP TYPE IF EXISTS "OrderStatus"')
    op.execute('DROP TYPE IF EXISTS "OrderType"')
    op.execute('DROP TYPE IF EXISTS "ReservationStatus"')
    op.execute('DROP TYPE IF EXISTS "TableStatus"')
    op.execute('DROP TYPE IF EXISTS "UserRole"')
