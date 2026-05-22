from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime


class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    allergenInfo: Optional[str] = Field(None, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)  # Protein, Vegetable, Spice, etc.
    isVegetarian: bool = False
    isVegan: bool = False
    isGlutenFree: bool = False
    isDairyFree: bool = False
    nutritionalInfo: Optional[dict] = None  # Calories, protein, carbs, etc.
    
    @validator('isVegan')
    def validate_vegan_vegetarian(cls, v, values):
        # If vegan is True, vegetarian should also be True
        if v and 'isVegetarian' in values and not values['isVegetarian']:
            values['isVegetarian'] = True
        return v


class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    allergenInfo: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    isVegetarian: Optional[bool] = None
    isVegan: Optional[bool] = None
    isGlutenFree: Optional[bool] = None
    isDairyFree: Optional[bool] = None
    nutritionalInfo: Optional[dict] = None
    isActive: Optional[bool] = None


class IngredientResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    allergenInfo: Optional[str] = None
    category: str
    isVegetarian: bool
    isVegan: bool
    isGlutenFree: bool
    isDairyFree: bool
    nutritionalInfo: Optional[dict] = None
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    dishCount: Optional[int] = 0  # Number of dishes using this ingredient
    
    class Config:
        from_attributes = True


class DishIngredientCreate(BaseModel):
    dishId: int
    ingredientId: int
    quantity: Optional[str] = Field(None, max_length=50)  # "2 cups", "1 tsp", etc.
    isOptional: bool = False
    isVisible: bool = True  # Whether to show in menu
    notes: Optional[str] = Field(None, max_length=200)


class DishIngredientUpdate(BaseModel):
    quantity: Optional[str] = Field(None, max_length=50)
    isOptional: Optional[bool] = None
    isVisible: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=200)


class DishIngredientResponse(BaseModel):
    id: int
    dishId: int
    dish: Optional[dict] = None
    ingredientId: int
    ingredient: Optional[dict] = None
    quantity: Optional[str] = None
    isOptional: bool
    isVisible: bool
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class DishIngredientsResponse(BaseModel):
    dishId: int
    dishName: str
    ingredients: List[DishIngredientResponse]
    allergens: List[str]  # Compiled allergen list
    dietaryInfo: dict  # Compiled dietary information


class IngredientSearchFilters(BaseModel):
    category: Optional[str] = None
    isVegetarian: Optional[bool] = None
    isVegan: Optional[bool] = None
    isGlutenFree: Optional[bool] = None
    isDairyFree: Optional[bool] = None
    hasAllergens: Optional[bool] = None
    isActive: Optional[bool] = True


class IngredientStatsResponse(BaseModel):
    totalIngredients: int
    activeIngredients: int
    categoriesCount: int
    vegetarianCount: int
    veganCount: int
    glutenFreeCount: int
    dairyFreeCount: int
    mostUsedIngredients: List[dict]  # Top 10 most used ingredients


class IngredientCategoryResponse(BaseModel):
    category: str
    ingredientCount: int
    vegetarianCount: int
    veganCount: int
    glutenFreeCount: int
    dairyFreeCount: int
