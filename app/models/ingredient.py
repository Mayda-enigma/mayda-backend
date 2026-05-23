from datetime import datetime

from pydantic import BaseModel, Field, validator


class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    allergenInfo: str | None = Field(None, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)  # Protein, Vegetable, Spice, etc.
    isVegetarian: bool = False
    isVegan: bool = False
    isGlutenFree: bool = False
    isDairyFree: bool = False
    nutritionalInfo: dict | None = None  # Calories, protein, carbs, etc.

    @validator("isVegan")
    def validate_vegan_vegetarian(cls, v, values):
        # If vegan is True, vegetarian should also be True
        if v and "isVegetarian" in values and not values["isVegetarian"]:
            values["isVegetarian"] = True
        return v


class IngredientUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    allergenInfo: str | None = Field(None, max_length=200)
    category: str | None = Field(None, min_length=1, max_length=50)
    isVegetarian: bool | None = None
    isVegan: bool | None = None
    isGlutenFree: bool | None = None
    isDairyFree: bool | None = None
    nutritionalInfo: dict | None = None
    isActive: bool | None = None


class IngredientResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    allergenInfo: str | None = None
    category: str
    isVegetarian: bool
    isVegan: bool
    isGlutenFree: bool
    isDairyFree: bool
    nutritionalInfo: dict | None = None
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    dishCount: int | None = 0  # Number of dishes using this ingredient

    class Config:
        from_attributes = True


class DishIngredientCreate(BaseModel):
    dishId: int
    ingredientId: int
    quantity: str | None = Field(None, max_length=50)  # "2 cups", "1 tsp", etc.
    isOptional: bool = False
    isVisible: bool = True  # Whether to show in menu
    notes: str | None = Field(None, max_length=200)


class DishIngredientUpdate(BaseModel):
    quantity: str | None = Field(None, max_length=50)
    isOptional: bool | None = None
    isVisible: bool | None = None
    notes: str | None = Field(None, max_length=200)


class DishIngredientResponse(BaseModel):
    id: int
    dishId: int
    dish: dict | None = None
    ingredientId: int
    ingredient: dict | None = None
    quantity: str | None = None
    isOptional: bool
    isVisible: bool
    notes: str | None = None

    class Config:
        from_attributes = True


class DishIngredientsResponse(BaseModel):
    dishId: int
    dishName: str
    ingredients: list[DishIngredientResponse]
    allergens: list[str]  # Compiled allergen list
    dietaryInfo: dict  # Compiled dietary information


class IngredientSearchFilters(BaseModel):
    category: str | None = None
    isVegetarian: bool | None = None
    isVegan: bool | None = None
    isGlutenFree: bool | None = None
    isDairyFree: bool | None = None
    hasAllergens: bool | None = None
    isActive: bool | None = True


class IngredientStatsResponse(BaseModel):
    totalIngredients: int
    activeIngredients: int
    categoriesCount: int
    vegetarianCount: int
    veganCount: int
    glutenFreeCount: int
    dairyFreeCount: int
    mostUsedIngredients: list[dict]  # Top 10 most used ingredients


class IngredientCategoryResponse(BaseModel):
    category: str
    ingredientCount: int
    vegetarianCount: int
    veganCount: int
    glutenFreeCount: int
    dairyFreeCount: int
