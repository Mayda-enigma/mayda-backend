from datetime import datetime

from pydantic import BaseModel, Field, validator


class InventoryItemCreate(BaseModel):
    restaurantId: int
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    category: str = Field(..., min_length=1, max_length=50)
    unit: str = Field(..., min_length=1, max_length=20)  # kg, lbs, pcs, liters, etc.
    currentStock: float = Field(..., ge=0)
    minimumStock: float = Field(..., ge=0)
    unitPrice: float = Field(..., ge=0)
    supplier: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)  # Storage location
    expiryDate: datetime | None = None


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, min_length=1, max_length=50)
    unit: str | None = Field(None, min_length=1, max_length=20)
    currentStock: float | None = Field(None, ge=0)
    minimumStock: float | None = Field(None, ge=0)
    unitPrice: float | None = Field(None, ge=0)
    supplier: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)
    expiryDate: datetime | None = None
    isActive: bool | None = None


class InventoryItemResponse(BaseModel):
    id: int
    restaurantId: int
    restaurant: dict | None = None
    name: str
    description: str | None = None
    category: str | None = None
    unit: str
    currentStock: float
    minimumStock: float
    unitPrice: float
    totalValue: float  # currentStock * unitPrice
    supplier: str | None = None
    location: str | None = None
    expiryDate: datetime | None = None
    isActive: bool
    isLowStock: bool  # currentStock <= minimumStock
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class InventoryStockUpdate(BaseModel):
    itemId: int
    quantityChange: float  # Positive for addition, negative for consumption
    reason: str = Field(..., min_length=1, max_length=200)
    notes: str | None = Field(None, max_length=500)

    @validator("quantityChange")
    def validate_quantity_change(cls, v):
        if v == 0:
            raise ValueError("Quantity change cannot be zero")
        return v


class InventoryStockUpdateResponse(BaseModel):
    success: bool
    previousStock: float
    newStock: float
    quantityChanged: float
    message: str


class InventoryStatsResponse(BaseModel):
    restaurantId: int
    restaurantName: str
    totalItems: int
    activeItems: int
    lowStockItems: int
    totalValue: float
    averageItemValue: float
    expiringSoonItems: int  # Items expiring in next 7 days
    categoriesCount: int
    suppliersCount: int


class InventoryLowStockAlert(BaseModel):
    id: int
    name: str
    category: str
    currentStock: float
    minimumStock: float
    unit: str
    supplier: str | None = None
    location: str | None = None
    expiryDate: datetime | None = None

    class Config:
        from_attributes = True


class InventorySearchFilters(BaseModel):
    category: str | None = None
    supplier: str | None = None
    location: str | None = None
    lowStockOnly: bool | None = False
    expiringSoon: bool | None = False  # Items expiring in next 7 days
    isActive: bool | None = True


class InventoryCategoryResponse(BaseModel):
    category: str
    itemCount: int
    totalValue: float
    lowStockCount: int


class InventorySupplierResponse(BaseModel):
    supplier: str
    itemCount: int
    totalValue: float
    lowStockCount: int
