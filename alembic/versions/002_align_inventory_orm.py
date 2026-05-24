"""Align inventory and loyalty_transactions with current ORM model.

Renames inventory columns (itemName -> name, minStock -> minimumStock,
unitCost -> unitPrice), drops deprecated columns, adds new columns,
adds orderId to loyalty_transactions, and creates ingredients /
dish_ingredients tables.

Revision ID: 002
Revises: fb6a4e84bc72
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: str | None = "fb6a4e84bc72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Inventory: rename columns ──────────────────────────────────
    op.alter_column("inventory", "itemName", new_column_name="name")
    op.alter_column("inventory", "minStock", new_column_name="minimumStock")
    op.alter_column("inventory", "unitCost", new_column_name="unitPrice")

    # unitCost was nullable; unitPrice is NOT NULL. Set any NULLs to 0.
    op.execute('UPDATE inventory SET "unitPrice" = 0 WHERE "unitPrice" IS NULL')
    op.alter_column("inventory", "unitPrice", nullable=False)

    # ── Inventory: add new columns ─────────────────────────────────
    op.add_column("inventory", sa.Column("category", sa.String(), nullable=True))
    op.add_column("inventory", sa.Column("location", sa.String(), nullable=True))
    op.add_column(
        "inventory",
        sa.Column("expiryDate", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory",
        sa.Column(
            "isActive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # ── Inventory: drop deprecated columns ─────────────────────────
    op.drop_column("inventory", "maxStock")
    op.drop_column("inventory", "supplierContact")
    op.drop_column("inventory", "lastRestocked")

    # ── Inventory: update unique constraint for renamed column ─────
    op.drop_constraint(
        "inventory_restaurantId_itemName_key",
        "inventory",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_inventory_restaurant_name",
        "inventory",
        ["restaurantId", "name"],
    )

    # ── Loyalty transactions: add orderId ──────────────────────────
    op.add_column(
        "loyalty_transactions",
        sa.Column("orderId", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "loyalty_transactions_orderId_fkey",
        "loyalty_transactions",
        "orders",
        ["orderId"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── Create ingredients table ───────────────────────────────────
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("allergenInfo", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column(
            "isVegetarian",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "isVegan",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "isGlutenFree",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "isDairyFree",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("nutritionalInfo", postgresql.JSONB(), nullable=True),
        sa.Column(
            "isActive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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

    # ── Create dish_ingredients table ──────────────────────────────
    op.create_table(
        "dish_ingredients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dishId", sa.Integer(), nullable=False),
        sa.Column("ingredientId", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column(
            "isOptional",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "isVisible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "dish_ingredients_dishId_fkey",
        "dish_ingredients",
        "dishes",
        ["dishId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "dish_ingredients_ingredientId_fkey",
        "dish_ingredients",
        "ingredients",
        ["ingredientId"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # ── Drop new tables ────────────────────────────────────────────
    op.drop_table("dish_ingredients")
    op.drop_table("ingredients")

    # ── Loyalty transactions: drop orderId ─────────────────────────
    op.drop_constraint(
        "loyalty_transactions_orderId_fkey",
        "loyalty_transactions",
        type_="foreignkey",
    )
    op.drop_column("loyalty_transactions", "orderId")

    # ── Inventory: drop new constraint (references "name") ─────────
    op.drop_constraint(
        "uq_inventory_restaurant_name",
        "inventory",
        type_="unique",
    )

    # ── Inventory: drop new columns ────────────────────────────────
    op.drop_column("inventory", "isActive")
    op.drop_column("inventory", "expiryDate")
    op.drop_column("inventory", "location")
    op.drop_column("inventory", "category")

    # ── Inventory: restore old columns ─────────────────────────────
    op.add_column(
        "inventory",
        sa.Column("lastRestocked", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory",
        sa.Column("supplierContact", sa.String(), nullable=True),
    )
    op.add_column("inventory", sa.Column("maxStock", sa.Float(), nullable=True))

    # ── Inventory: revert column names and nullability ─────────────
    op.alter_column("inventory", "unitPrice", nullable=True)
    op.alter_column("inventory", "unitPrice", new_column_name="unitCost")
    op.alter_column("inventory", "minimumStock", new_column_name="minStock")
    op.alter_column("inventory", "name", new_column_name="itemName")

    # ── Inventory: restore old unique constraint ───────────────────
    op.create_unique_constraint(
        "inventory_restaurantId_itemName_key",
        "inventory",
        ["restaurantId", "itemName"],
    )
