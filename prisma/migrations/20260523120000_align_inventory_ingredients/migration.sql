ALTER TABLE "inventory"
ADD COLUMN "name" TEXT,
ADD COLUMN "category" TEXT,
ADD COLUMN "minimumStock" DOUBLE PRECISION,
ADD COLUMN "unitPrice" DOUBLE PRECISION,
ADD COLUMN "location" TEXT,
ADD COLUMN "expiryDate" TIMESTAMP(3),
ADD COLUMN "isActive" BOOLEAN NOT NULL DEFAULT true;

UPDATE "inventory"
SET
  "name" = COALESCE("name", "itemName"),
  "minimumStock" = COALESCE("minimumStock", "minStock"),
  "unitPrice" = COALESCE("unitPrice", "unitCost", 0);

ALTER TABLE "ingredient"
ADD COLUMN "name" TEXT,
ADD COLUMN "description" TEXT,
ADD COLUMN "allergenInfo" TEXT,
ADD COLUMN "category" TEXT,
ADD COLUMN "isVegetarian" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN "isVegan" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN "isGlutenFree" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN "isDairyFree" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN "nutritionalInfo" JSONB,
ADD COLUMN "isActive" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

UPDATE "ingredient" AS i
SET
  "name" = COALESCE(i."name", inv."itemName"),
  "description" = COALESCE(i."description", inv."description"),
  "category" = COALESCE(i."category", 'Uncategorized')
FROM "inventory" AS inv
WHERE i."InventoryId" = inv."id";

ALTER TABLE "ingredient"
ALTER COLUMN "dishId" DROP NOT NULL,
ALTER COLUMN "InventoryId" DROP NOT NULL,
ALTER COLUMN "quantity" DROP NOT NULL;
