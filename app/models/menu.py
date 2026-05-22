from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Menu Models
class MenuBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    isActive: bool = True
    displayOrder: int = Field(0, ge=0)


class MenuCreate(MenuBase):
    restaurantId: int


class MenuUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    isActive: Optional[bool] = None
    displayOrder: Optional[int] = Field(None, ge=0)


class MenuResponse(BaseModel):
    id: int
    restaurantId: int
    name: str
    description: Optional[str]
    isActive: bool
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


# Menu Category Models
class MenuCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    image: Optional[str] = None
    isActive: bool = True
    displayOrder: int = Field(0, ge=0)


class MenuCategoryCreate(MenuCategoryBase):
    menuId: int


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    image: Optional[str] = None
    isActive: Optional[bool] = None
    displayOrder: Optional[int] = Field(None, ge=0)


class MenuCategoryResponse(BaseModel):
    id: int
    menuId: int
    name: str
    description: Optional[str]
    image: Optional[str]
    isActive: bool
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


# Dish Models
class DishBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    image: Optional[str] = None
    gallery: Optional[List[str]] = []
    isAvailable: bool = True
    quantity: int = Field(..., ge=0)
    preparationTime: int = Field(..., ge=1, description="Preparation time in minutes")
    popularity: float = Field(0, ge=0, le=5)
    displayOrder: int = Field(0, ge=0)


class DishCreate(DishBase):
    categoryId: int


class DishUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    price: Optional[float] = Field(None, gt=0)
    image: Optional[str] = None
    gallery: Optional[List[str]] = None
    isAvailable: Optional[bool] = None
    quantity: Optional[int] = Field(None, ge=0)
    preparationTime: Optional[int] = Field(None, ge=1)
    popularity: Optional[float] = Field(None, ge=0, le=5)
    displayOrder: Optional[int] = Field(None, ge=0)


class DishResponse(BaseModel):
    id: int
    categoryId: int
    name: str
    description: str
    price: float
    image: Optional[str]
    gallery: List[str]
    isAvailable: bool
    quantity: int
    preparationTime: int
    popularity: float
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class DishListResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    image: Optional[str]
    isAvailable: bool
    quantity: int
    preparationTime: int
    popularity: float
    
    class Config:
        from_attributes = True


# Full Menu Response with Categories and Dishes
class MenuCategoryWithDishes(BaseModel):
    id: int
    name: str
    description: Optional[str]
    image: Optional[str]
    isActive: bool
    displayOrder: int
    dishes: List[DishListResponse]
    
    class Config:
        from_attributes = True


class MenuWithCategories(BaseModel):
    id: int
    name: str
    description: Optional[str]
    isActive: bool
    displayOrder: int
    categories: List[MenuCategoryWithDishes]
    
    class Config:
        from_attributes = True
