-- CreateEnum
CREATE TYPE "TableStatus" AS ENUM ('AVAILABLE', 'OCCUPIED');

-- AlterTable
ALTER TABLE "tables" ADD COLUMN "status" "TableStatus" NOT NULL DEFAULT 'AVAILABLE';

-- CreateTable
CREATE TABLE "table_sessions" (
    "id" SERIAL NOT NULL,
    "tableId" INTEGER NOT NULL,
    "waiterId" INTEGER NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endedAt" TIMESTAMP(3),
    "isActive" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "table_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "table_sessions_tableId_isActive_idx" ON "table_sessions"("tableId", "isActive");

-- CreateIndex
CREATE INDEX "table_sessions_waiterId_isActive_idx" ON "table_sessions"("waiterId", "isActive");

-- AddForeignKey
ALTER TABLE "table_sessions" ADD CONSTRAINT "table_sessions_tableId_fkey" FOREIGN KEY ("tableId") REFERENCES "tables"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "table_sessions" ADD CONSTRAINT "table_sessions_waiterId_fkey" FOREIGN KEY ("waiterId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
