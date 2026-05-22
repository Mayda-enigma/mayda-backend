from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime


class InventoryItemCreate(BaseModel):
    restaurantId: int
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    category: str = Field(..., min_length=1, max_length=50)
    unit: str = Field(..., min_length=1, max_length=20)  # kg, lbs, pcs, liters, etc.
    currentStock: float = Field(..., ge=0)
    minimumStock: float = Field(..., ge=0)
    unitPrice: float = Field(..., ge=0)
    supplier: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=100)  # Storage location
    expiryDate: Optional[datetime] = None
    
    @validator('minimumStock')
    def validate_minimum_stock(cls, v, values):
        if 'currentStock' in values and v > values['currentStock']:
            raise ValueError('Minimum stock cannot be greater than current stock')
        return v


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    currentStock: Optional[float] = Field(None, ge=0)
    minimumStock: Optional[float] = Field(None, ge=0)
    unitPrice: Optional[float] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=100)
    expiryDate: Optional[datetime] = None
    isActive: Optional[bool] = None


class InventoryItemResponse(BaseModel):
    id: int
    restaurantId: int
    restaurant: Optional[dict] = None
    name: str
    description: Optional[str] = None
    category: str
    unit: str
    currentStock: float
    minimumStock: float
    unitPrice: float
    totalValue: float  # currentStock * unitPrice
    supplier: Optional[str] = None
    location: Optional[str] = None
    expiryDate: Optional[datetime] = None
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
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('quantityChange')
    def validate_quantity_change(cls, v):
        if v == 0:
            raise ValueError('Quantity change cannot be zero')
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
    supplier: Optional[str] = None
    location: Optional[str] = None
    expiryDate: Optional[datetime] = None


class InventorySearchFilters(BaseModel):
    category: Optional[str] = None
    supplier: Optional[str] = None
    location: Optional[str] = None
    lowStockOnly: Optional[bool] = False
    expiringSoon: Optional[bool] = False  # Items expiring in next 7 days
    isActive: Optional[bool] = True


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
