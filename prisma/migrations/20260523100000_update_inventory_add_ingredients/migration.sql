-- ============================================================
-- Migration: update_inventory_add_ingredients
-- Renames Inventory columns, adds new ones, drops the old
-- ingredient join table and replaces it with a proper
-- Ingredient entity + two new join tables.
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- 1. Update `inventory` table
-- ──────────────────────────────────────────────────────────────

-- Drop old unique constraint on [restaurantId, itemName]
ALTER TABLE "inventory" DROP CONSTRAINT IF EXISTS "inventory_restaurantId_itemName_key";

-- Rename columns to match new schema
ALTER TABLE "inventory" RENAME COLUMN "itemName" TO "name";
ALTER TABLE "inventory" RENAME COLUMN "minStock" TO "minimumStock";
ALTER TABLE "inventory" RENAME COLUMN "unitCost" TO "unitPrice";

-- Add missing columns
ALTER TABLE "inventory" ADD COLUMN IF NOT EXISTS "category" TEXT;
ALTER TABLE "inventory" ADD COLUMN IF NOT EXISTS "location"  TEXT;
ALTER TABLE "inventory" ADD COLUMN IF NOT EXISTS "expiryDate" TIMESTAMP(3);
ALTER TABLE "inventory" ADD COLUMN IF NOT EXISTS "isActive" BOOLEAN NOT NULL DEFAULT true;

-- unitPrice was nullable before; backfill zeros and make NOT NULL
UPDATE "inventory" SET "unitPrice" = 0 WHERE "unitPrice" IS NULL;
ALTER TABLE "inventory" ALTER COLUMN "unitPrice" SET NOT NULL;
ALTER TABLE "inventory" ALTER COLUMN "unitPrice" SET DEFAULT 0;

-- category was added as nullable; backfill and enforce NOT NULL
UPDATE "inventory" SET "category" = 'other' WHERE "category" IS NULL;
ALTER TABLE "inventory" ALTER COLUMN "category" SET NOT NULL;

-- Re-create unique constraint on new column name
ALTER TABLE "inventory" ADD CONSTRAINT "inventory_restaurantId_name_key"
    UNIQUE ("restaurantId", "name");

-- ──────────────────────────────────────────────────────────────
-- 2. Drop the old `ingredient` join table (dish ↔ inventory)
-- ──────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS "ingredient";

-- ──────────────────────────────────────────────────────────────
-- 3. Create the new standalone `ingredients` table
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS "ingredients" (
    "id"              SERIAL       NOT NULL,
    "name"            TEXT         NOT NULL,
    "description"     TEXT,
    "allergenInfo"    TEXT,
    "category"        TEXT         NOT NULL,
    "isVegetarian"    BOOLEAN      NOT NULL DEFAULT false,
    "isVegan"         BOOLEAN      NOT NULL DEFAULT false,
    "isGlutenFree"    BOOLEAN      NOT NULL DEFAULT false,
    "isDairyFree"     BOOLEAN      NOT NULL DEFAULT false,
    "nutritionalInfo" JSONB,
    "isActive"        BOOLEAN      NOT NULL DEFAULT true,
    "createdAt"       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ingredients_pkey" PRIMARY KEY ("id")
);

-- ──────────────────────────────────────────────────────────────
-- 4. Create `dish_inventory` (DishIngredient: dish ↔ inventory)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS "dish_inventory" (
    "id"          SERIAL           NOT NULL,
    "dishId"      INTEGER          NOT NULL,
    "inventoryId" INTEGER          NOT NULL,
    "quantity"    DOUBLE PRECISION NOT NULL,

    CONSTRAINT "dish_inventory_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "dish_inventory"
    ADD CONSTRAINT "dish_inventory_dishId_fkey"
    FOREIGN KEY ("dishId") REFERENCES "dishes"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "dish_inventory"
    ADD CONSTRAINT "dish_inventory_inventoryId_fkey"
    FOREIGN KEY ("inventoryId") REFERENCES "inventory"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- ──────────────────────────────────────────────────────────────
-- 5. Create `dish_ingredients` (DishIngredientLink: dish ↔ ingredient)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS "dish_ingredients" (
    "id"           SERIAL       NOT NULL,
    "dishId"       INTEGER      NOT NULL,
    "ingredientId" INTEGER      NOT NULL,
    "quantity"     TEXT,
    "isOptional"   BOOLEAN      NOT NULL DEFAULT false,
    "isVisible"    BOOLEAN      NOT NULL DEFAULT true,
    "notes"        TEXT,

    CONSTRAINT "dish_ingredients_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "dish_ingredients"
    ADD CONSTRAINT "dish_ingredients_dishId_fkey"
    FOREIGN KEY ("dishId") REFERENCES "dishes"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "dish_ingredients"
    ADD CONSTRAINT "dish_ingredients_ingredientId_fkey"
    FOREIGN KEY ("ingredientId") REFERENCES "ingredients"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS "dish_ingredients_dishId_ingredientId_key"
    ON "dish_ingredients"("dishId", "ingredientId");
