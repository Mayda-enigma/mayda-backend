/*
  Warnings:

  - You are about to drop the column `amount` on the `payments` table. All the data in the column will be lost.
  - You are about to drop the column `externalId` on the `payments` table. All the data in the column will be lost.
  - You are about to drop the column `method` on the `payments` table. All the data in the column will be lost.
  - You are about to drop the column `providerResponse` on the `payments` table. All the data in the column will be lost.
  - You are about to drop the column `status` on the `payments` table. All the data in the column will be lost.
  - You are about to drop the column `updatedAt` on the `payments` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[paymentId]` on the table `payments` will be added. If there are existing duplicate values, this will fail.
  - A unique constraint covering the columns `[orderId]` on the table `payments` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `paymentId` to the `payments` table without a default value. This is not possible if the table is not empty.

*/
-- DropForeignKey
ALTER TABLE "payments" DROP CONSTRAINT "payments_orderId_fkey";

-- AlterTable
ALTER TABLE "orders" ADD COLUMN     "paymentId" INTEGER;

-- AlterTable
ALTER TABLE "payments" DROP COLUMN "amount",
DROP COLUMN "externalId",
DROP COLUMN "method",
DROP COLUMN "providerResponse",
DROP COLUMN "status",
DROP COLUMN "updatedAt",
ADD COLUMN     "paymentId" TEXT NOT NULL;

-- DropEnum
DROP TYPE "PaymentMethod";

-- CreateIndex
CREATE UNIQUE INDEX "payments_paymentId_key" ON "payments"("paymentId");

-- CreateIndex
CREATE UNIQUE INDEX "payments_orderId_key" ON "payments"("orderId");

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "payments_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "orders"("id") ON DELETE CASCADE ON UPDATE CASCADE;
