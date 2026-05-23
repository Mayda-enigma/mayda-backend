from datetime import datetime

from pydantic import BaseModel, Field


# Menu Models
class MenuBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    isActive: bool = True
    displayOrder: int = Field(0, ge=0)


class MenuCreate(MenuBase):
    restaurantId: int


class MenuUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    isActive: bool | None = None
    displayOrder: int | None = Field(None, ge=0)


class MenuResponse(BaseModel):
    id: int
    restaurantId: int
    name: str
    description: str | None
    isActive: bool
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


# Menu Category Models
class MenuCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    image: str | None = None
    isActive: bool = True
    displayOrder: int = Field(0, ge=0)


class MenuCategoryCreate(MenuCategoryBase):
    menuId: int


class MenuCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    image: str | None = None
    isActive: bool | None = None
    displayOrder: int | None = Field(None, ge=0)


class MenuCategoryResponse(BaseModel):
    id: int
    menuId: int
    name: str
    description: str | None
    image: str | None
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
    image: str | None = None
    gallery: list[str] | None = []
    isAvailable: bool = True
    quantity: int = Field(..., ge=0)
    preparationTime: int = Field(..., ge=1, description="Preparation time in minutes")
    popularity: float = Field(0, ge=0, le=5)
    displayOrder: int = Field(0, ge=0)


class DishCreate(DishBase):
    categoryId: int


class DishUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    price: float | None = Field(None, gt=0)
    image: str | None = None
    gallery: list[str] | None = None
    isAvailable: bool | None = None
    quantity: int | None = Field(None, ge=0)
    preparationTime: int | None = Field(None, ge=1)
    popularity: float | None = Field(None, ge=0, le=5)
    displayOrder: int | None = Field(None, ge=0)


class DishResponse(BaseModel):
    id: int
    categoryId: int
    name: str
    description: str
    price: float
    image: str | None
    gallery: list[str]
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
    image: str | None
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
    description: str | None
    image: str | None
    isActive: bool
    displayOrder: int
    dishes: list[DishListResponse]

    class Config:
        from_attributes = True


class MenuWithCategories(BaseModel):
    id: int
    name: str
    description: str | None
    isActive: bool
    displayOrder: int
    categories: list[MenuCategoryWithDishes]

    class Config:
        from_attributes = True
