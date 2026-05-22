from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.models.ingredient import (
    IngredientCreate, IngredientUpdate, IngredientResponse,
    DishIngredientCreate, DishIngredientUpdate, DishIngredientResponse,
    DishIngredientsResponse, IngredientSearchFilters, IngredientStatsResponse,
    IngredientCategoryResponse
)
from app.core.database import get_db
from app.middleware.roles import (
    get_current_staff_user, get_admin_user, get_manager_user
)


router = APIRouter(prefix="/ingredients", tags=["Ingredients Management"])


# ==================== INGREDIENTS CRUD ====================

@router.post("/", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
async def create_ingredient(
    ingredient_data: IngredientCreate,
    current_user = Depends(get_current_staff_user)
):
    """Create new ingredient (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create ingredients"
        )
    
    # Check if ingredient with same name already exists
    existing_ingredient = await db.ingredient.find_first(
        where={
            "name": ingredient_data.name,
            "isActive": True
        }
    )
    
    if existing_ingredient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingredient '{ingredient_data.name}' already exists"
        )
    
    try:
        # Create ingredient
        ingredient = await db.ingredient.create(
            data={
                "name": ingredient_data.name,
                "description": ingredient_data.description,
                "allergenInfo": ingredient_data.allergenInfo,
                "category": ingredient_data.category,
                "isVegetarian": ingredient_data.isVegetarian,
                "isVegan": ingredient_data.isVegan,
                "isGlutenFree": ingredient_data.isGlutenFree,
                "isDairyFree": ingredient_data.isDairyFree,
                "nutritionalInfo": ingredient_data.nutritionalInfo
            }
        )
        
        # Format response
        ingredient_dict = ingredient.__dict__.copy()
        ingredient_dict["dishCount"] = 0  # New ingredient has no dishes yet
        
        return IngredientResponse.model_validate(ingredient_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating ingredient: {str(e)}"
        )


@router.get("/", response_model=List[IngredientResponse])
async def get_ingredients(
    category: Optional[str] = Query(None),
    is_vegetarian: Optional[bool] = Query(None),
    is_vegan: Optional[bool] = Query(None),
    is_gluten_free: Optional[bool] = Query(None),
    is_dairy_free: Optional[bool] = Query(None),
    has_allergens: Optional[bool] = Query(None),
    is_active: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_staff_user)
):
    """Get ingredients with filters (Staff only)."""
    db = get_db()
    
    # Build where clause
    where_clause = {"isActive": is_active}
    
    if category:
        where_clause["category"] = category
    
    if is_vegetarian is not None:
        where_clause["isVegetarian"] = is_vegetarian
    
    if is_vegan is not None:
        where_clause["isVegan"] = is_vegan
    
    if is_gluten_free is not None:
        where_clause["isGlutenFree"] = is_gluten_free
    
    if is_dairy_free is not None:
        where_clause["isDairyFree"] = is_dairy_free
    
    if has_allergens is not None:
        if has_allergens:
            where_clause["allergenInfo"] = {"not": None}
        else:
            where_clause["allergenInfo"] = None
    
    try:
        ingredients = await db.ingredient.find_many(
            where=where_clause,
            skip=skip,
            take=limit,
            order={"name": "asc"}
        )
        
        # Get dish count for each ingredient
        result = []
        for ingredient in ingredients:
            # Count dishes using this ingredient
            dish_count = await db.dish.count(
                where={
                    "ingredients": {
                        "some": {
                            "ingredientId": ingredient.id
                        }
                    }
                }
            )
            
            ingredient_dict = ingredient.__dict__.copy()
            ingredient_dict["dishCount"] = dish_count
            
            result.append(IngredientResponse.model_validate(ingredient_dict))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching ingredients: {str(e)}"
        )


@router.get("/{ingredient_id}", response_model=IngredientResponse)
async def get_ingredient(
    ingredient_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Get single ingredient (Staff only)."""
    db = get_db()
    
    # Get ingredient
    ingredient = await db.ingredient.find_unique(
        where={"id": ingredient_id}
    )
    
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )
    
    # Count dishes using this ingredient
    dish_count = await db.dish.count(
        where={
            "ingredients": {
                "some": {
                    "ingredientId": ingredient_id
                }
            }
        }
    )
    
    ingredient_dict = ingredient.__dict__.copy()
    ingredient_dict["dishCount"] = dish_count
    
    return IngredientResponse.model_validate(ingredient_dict)


@router.put("/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: int,
    ingredient_data: IngredientUpdate,
    current_user = Depends(get_current_staff_user)
):
    """Update ingredient (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can update ingredients"
        )
    
    # Get ingredient
    ingredient = await db.ingredient.find_unique(
        where={"id": ingredient_id}
    )
    
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )
    
    # Prepare update data
    update_data = {}
    for field, value in ingredient_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Check for name conflicts if name is being updated
    if "name" in update_data:
        existing_ingredient = await db.ingredient.find_first(
            where={
                "name": update_data["name"],
                "id": {"not": ingredient_id},
                "isActive": True
            }
        )
        
        if existing_ingredient:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ingredient '{update_data['name']}' already exists"
            )
    
    try:
        # Update ingredient
        updated_ingredient = await db.ingredient.update(
            where={"id": ingredient_id},
            data=update_data
        )
        
        # Count dishes using this ingredient
        dish_count = await db.dish.count(
            where={
                "ingredients": {
                    "some": {
                        "ingredientId": ingredient_id
                    }
                }
            }
        )
        
        ingredient_dict = updated_ingredient.__dict__.copy()
        ingredient_dict["dishCount"] = dish_count
        
        return IngredientResponse.model_validate(ingredient_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating ingredient: {str(e)}"
        )


@router.delete("/{ingredient_id}")
async def delete_ingredient(
    ingredient_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Delete (deactivate) ingredient (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can delete ingredients"
        )
    
    # Get ingredient
    ingredient = await db.ingredient.find_unique(
        where={"id": ingredient_id}
    )
    
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )
    
    # Check if ingredient is used in any dishes
    dish_count = await db.dish.count(
        where={
            "ingredients": {
                "some": {
                    "ingredientId": ingredient_id
                }
            }
        }
    )
    
    if dish_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete ingredient '{ingredient.name}' as it is used in {dish_count} dish(es). Remove from dishes first."
        )
    
    try:
        # Soft delete by setting isActive to False
        await db.ingredient.update(
            where={"id": ingredient_id},
            data={"isActive": False}
        )
        
        return {"message": f"Ingredient '{ingredient.name}' has been deactivated"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting ingredient: {str(e)}"
        )


# ==================== DISH INGREDIENTS MANAGEMENT ====================

@router.post("/dish-ingredients", response_model=DishIngredientResponse, status_code=status.HTTP_201_CREATED)
async def add_ingredient_to_dish(
    dish_ingredient_data: DishIngredientCreate,
    current_user = Depends(get_current_staff_user)
):
    """Add ingredient to dish (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can manage dish ingredients"
        )
    
    # Validate dish exists and user has access
    dish = await db.dish.find_unique(
        where={"id": dish_ingredient_data.dishId},
        include={
            "category": {
                "include": {
                    "menu": {
                        "include": {
                            "restaurant": True
                        }
                    }
                }
            }
        }
    )
    
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Check if user can manage this restaurant's dishes
    restaurant_id = dish.category.menu.restaurant.id
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage ingredients for dishes in your own restaurant"
        )
    
    # Validate ingredient exists
    ingredient = await db.ingredient.find_unique(
        where={
            "id": dish_ingredient_data.ingredientId,
            "isActive": True
        }
    )
    
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found or inactive"
        )
    
    # Check if ingredient is already added to this dish
    existing_relation = await db.dish.find_first(
        where={
            "id": dish_ingredient_data.dishId,
            "ingredients": {
                "some": {
                    "ingredientId": dish_ingredient_data.ingredientId
                }
            }
        }
    )
    
    if existing_relation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingredient '{ingredient.name}' is already added to this dish"
        )
    
    try:
        # Create dish-ingredient relation
        dish_ingredient = await db.ingredient.create(
            data={
                "dishId": dish_ingredient_data.dishId,
                "ingredientId": dish_ingredient_data.ingredientId,
                "quantity": dish_ingredient_data.quantity,
                "isOptional": dish_ingredient_data.isOptional,
                "isVisible": dish_ingredient_data.isVisible,
                "notes": dish_ingredient_data.notes
            },
            include={
                "dish": {
                    "select": {
                        "name": True
                    }
                },
                "ingredient": {
                    "select": {
                        "name": True,
                        "category": True
                    }
                }
            }
        )
        
        return DishIngredientResponse.model_validate(dish_ingredient)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error adding ingredient to dish: {str(e)}"
        )


@router.get("/dish/{dish_id}/ingredients", response_model=DishIngredientsResponse)
async def get_dish_ingredients(
    dish_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Get all ingredients for a dish with dietary info (Staff only)."""
    db = get_db()
    
    # Get dish with ingredients
    dish = await db.dish.find_unique(
        where={"id": dish_id},
        include={
            "ingredients": {
                "include": {
                    "ingredient": True
                }
            },
            "category": {
                "include": {
                    "menu": {
                        "include": {
                            "restaurant": True
                        }
                    }
                }
            }
        }
    )
    
    if not dish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found"
        )
    
    # Check permissions for restaurant access
    restaurant_id = dish.category.menu.restaurant.id
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view ingredients for dishes in your own restaurant"
        )
    
    # Format ingredients response
    ingredients = []
    allergens = set()
    
    # Dietary info compilation
    is_vegetarian = True
    is_vegan = True
    is_gluten_free = True
    is_dairy_free = True
    
    for dish_ingredient in dish.ingredients:
        ingredient = dish_ingredient.ingredient
        
        # Add to response
        ingredient_dict = dish_ingredient.__dict__.copy()
        ingredients.append(DishIngredientResponse.model_validate(ingredient_dict))
        
        # Collect allergens
        if ingredient.allergenInfo:
            allergens.update(ingredient.allergenInfo.split(", "))
        
        # Update dietary info (only required ingredients affect dietary classification)
        if not dish_ingredient.isOptional:
            if not ingredient.isVegetarian:
                is_vegetarian = False
            if not ingredient.isVegan:
                is_vegan = False
            if not ingredient.isGlutenFree:
                is_gluten_free = False
            if not ingredient.isDairyFree:
                is_dairy_free = False
    
    dietary_info = {
        "isVegetarian": is_vegetarian,
        "isVegan": is_vegan,
        "isGlutenFree": is_gluten_free,
        "isDairyFree": is_dairy_free
    }
    
    return DishIngredientsResponse(
        dishId=dish_id,
        dishName=dish.name,
        ingredients=ingredients,
        allergens=list(allergens),
        dietaryInfo=dietary_info
    )


@router.put("/dish-ingredients/{dish_ingredient_id}", response_model=DishIngredientResponse)
async def update_dish_ingredient(
    dish_ingredient_id: int,
    update_data: DishIngredientUpdate,
    current_user = Depends(get_current_staff_user)
):
    """Update dish ingredient relation (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can update dish ingredients"
        )
    
    # Get dish ingredient relation
    dish_ingredient = await db.ingredient.find_unique(
        where={"id": dish_ingredient_id},
        include={
            "dish": {
                "include": {
                    "category": {
                        "include": {
                            "menu": {
                                "include": {
                                    "restaurant": True
                                }
                            }
                        }
                    }
                }
            }
        }
    )
    
    if not dish_ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish ingredient relation not found"
        )
    
    # Check if user can manage this restaurant's dishes
    restaurant_id = dish_ingredient.dish.category.menu.restaurant.id
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update ingredients for dishes in your own restaurant"
        )
    
    # Prepare update data
    update_fields = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_fields[field] = value
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    try:
        # Update dish ingredient relation
        updated_relation = await db.ingredient.update(
            where={"id": dish_ingredient_id},
            data=update_fields,
            include={
                "dish": {
                    "select": {
                        "name": True
                    }
                },
                "ingredient": {
                    "select": {
                        "name": True,
                        "category": True
                    }
                }
            }
        )
        
        return DishIngredientResponse.model_validate(updated_relation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating dish ingredient: {str(e)}"
        )


@router.delete("/dish-ingredients/{dish_ingredient_id}")
async def remove_ingredient_from_dish(
    dish_ingredient_id: int,
    current_user = Depends(get_current_staff_user)
):
    """Remove ingredient from dish (Manager/Admin only)."""
    db = get_db()
    
    # Check permissions
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can remove dish ingredients"
        )
    
    # Get dish ingredient relation
    dish_ingredient = await db.ingredient.find_unique(
        where={"id": dish_ingredient_id},
        include={
            "dish": {
                "include": {
                    "category": {
                        "include": {
                            "menu": {
                                "include": {
                                    "restaurant": True
                                }
                            }
                        }
                    }
                }
            },
            "ingredient": True
        }
    )
    
    if not dish_ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish ingredient relation not found"
        )
    
    # Check if user can manage this restaurant's dishes
    restaurant_id = dish_ingredient.dish.category.menu.restaurant.id
    if current_user.role != "ADMIN" and current_user.restaurantId != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove ingredients from dishes in your own restaurant"
        )
    
    try:
        # Delete dish ingredient relation
        await db.ingredient.delete(
            where={"id": dish_ingredient_id}
        )
        
        return {
            "message": f"Ingredient '{dish_ingredient.ingredient.name}' removed from dish '{dish_ingredient.dish.name}'"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error removing ingredient from dish: {str(e)}"
        )


# ==================== ANALYTICS & REPORTING ====================

@router.get("/stats", response_model=IngredientStatsResponse)
async def get_ingredient_stats(
    current_user = Depends(get_current_staff_user)
):
    """Get ingredient statistics (Staff only)."""
    db = get_db()
    
    try:
        # Get all ingredients
        all_ingredients = await db.ingredient.find_many()
        active_ingredients = [ing for ing in all_ingredients if ing.isActive]
        
        # Count dietary types
        vegetarian_count = len([ing for ing in active_ingredients if ing.isVegetarian])
        vegan_count = len([ing for ing in active_ingredients if ing.isVegan])
        gluten_free_count = len([ing for ing in active_ingredients if ing.isGlutenFree])
        dairy_free_count = len([ing for ing in active_ingredients if ing.isDairyFree])
        
        # Count unique categories
        categories = set(ing.category for ing in active_ingredients if ing.category)
        
        # Get most used ingredients
        most_used = []
        for ingredient in active_ingredients:
            dish_count = await db.dish.count(
                where={
                    "ingredients": {
                        "some": {
                            "ingredientId": ingredient.id
                        }
                    }
                }
            )
            
            if dish_count > 0:
                most_used.append({
                    "id": ingredient.id,
                    "name": ingredient.name,
                    "category": ingredient.category,
                    "dishCount": dish_count
                })
        
        # Sort by usage and take top 10
        most_used.sort(key=lambda x: x["dishCount"], reverse=True)
        most_used = most_used[:10]
        
        return IngredientStatsResponse(
            totalIngredients=len(all_ingredients),
            activeIngredients=len(active_ingredients),
            categoriesCount=len(categories),
            vegetarianCount=vegetarian_count,
            veganCount=vegan_count,
            glutenFreeCount=gluten_free_count,
            dairyFreeCount=dairy_free_count,
            mostUsedIngredients=most_used
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error calculating ingredient stats: {str(e)}"
        )


@router.get("/categories", response_model=List[IngredientCategoryResponse])
async def get_ingredient_categories(
    current_user = Depends(get_current_staff_user)
):
    """Get ingredient breakdown by category (Staff only)."""
    db = get_db()
    
    try:
        # Get all active ingredients
        ingredients = await db.ingredient.find_many(
            where={"isActive": True}
        )
        
        # Group by category
        category_data = {}
        for ingredient in ingredients:
            category = ingredient.category or "Uncategorized"
            
            if category not in category_data:
                category_data[category] = {
                    "category": category,
                    "ingredientCount": 0,
                    "vegetarianCount": 0,
                    "veganCount": 0,
                    "glutenFreeCount": 0,
                    "dairyFreeCount": 0
                }
            
            data = category_data[category]
            data["ingredientCount"] += 1
            
            if ingredient.isVegetarian:
                data["vegetarianCount"] += 1
            if ingredient.isVegan:
                data["veganCount"] += 1
            if ingredient.isGlutenFree:
                data["glutenFreeCount"] += 1
            if ingredient.isDairyFree:
                data["dairyFreeCount"] += 1
        
        # Convert to response format
        result = [
            IngredientCategoryResponse.model_validate(data)
            for data in category_data.values()
        ]
        
        return sorted(result, key=lambda x: x.ingredientCount, reverse=True)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching category breakdown: {str(e)}"
        )
