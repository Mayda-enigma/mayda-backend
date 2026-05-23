import asyncio
import json
from prisma import Prisma
from datetime import datetime, timedelta
import random

async def main():
    db = Prisma()
    await db.connect()

    print("🚀 Starting database seeding...")

    # Clean up volatile data (orders, reviews, etc.) for idempotent re-seeding
    await db.loyaltytransaction.delete_many()
    await db.review.delete_many()
    await db.orderitem.delete_many()
    await db.order.delete_many()
    await db.reservation.delete_many()
    await db.dishingredientlink.delete_many()
    await db.dishingredient.delete_many()
    await db.ingredient.delete_many()
    await db.promotion.delete_many()
    await db.loyaltycard.delete_many()
    await db.dish.delete_many()
    await db.menucategory.delete_many()
    await db.menu.delete_many()
    await db.table.delete_many()
    await db.inventory.delete_many()
    print("🧹 Cleaned up existing orders, reviews, reservations, and dependent data")

    # 1. Create Multiple Restaurants (check if they exist first)
    existing_restaurants = await db.restaurant.find_many()
    if existing_restaurants:
        print(f"ℹ️  Found {len(existing_restaurants)} existing restaurants, using them")
        restaurants = existing_restaurants
    else:
        restaurants_data = [
            {
                'name': 'Caravane Downtown',
                'phone': '0123456789',
                'email': 'downtown@caravane.com',
                'operatingHours': json.dumps({'monday': '08:00-23:00', 'tuesday': '08:00-23:00', 'wednesday': '08:00-23:00', 'thursday': '08:00-23:00', 'friday': '08:00-23:00', 'saturday': '08:00-23:00', 'sunday': '08:00-23:00'}),
                'description': 'Trendy downtown location with modern international cuisine and craft cocktails.'
            },
            {
                'name': 'Caravane Beachside',
                'phone': '0987654321',
                'email': 'beachside@caravane.com',
                'operatingHours': json.dumps({'monday': '07:00-24:00', 'tuesday': '07:00-24:00', 'wednesday': '07:00-24:00', 'thursday': '07:00-24:00', 'friday': '07:00-24:00', 'saturday': '07:00-24:00', 'sunday': '07:00-24:00'}),
                'description': 'Oceanfront dining with fresh seafood and Mediterranean flavors.'
            },
            {
                'name': 'Caravane Gardens',
                'phone': '0555123456',
                'email': 'gardens@caravane.com',
                'operatingHours': json.dumps({'monday': '09:00-22:00', 'tuesday': '09:00-22:00', 'wednesday': '09:00-22:00', 'thursday': '09:00-22:00', 'friday': '09:00-22:00', 'saturday': '09:00-22:00', 'sunday': '09:00-22:00'}),
                'description': 'Garden-to-table restaurant focusing on organic, locally sourced ingredients.'
            },
            {
                'name': 'Caravane Rooftop',
                'phone': '0444567890',
                'email': 'rooftop@caravane.com',
                'operatingHours': json.dumps({'monday': '17:00-02:00', 'tuesday': '17:00-02:00', 'wednesday': '17:00-02:00', 'thursday': '17:00-02:00', 'friday': '17:00-02:00', 'saturday': '17:00-02:00', 'sunday': '17:00-02:00'}),
                'description': 'Upscale rooftop dining with panoramic city views and innovative cuisine.'
            }
        ]

        restaurants = []
        for restaurant_data in restaurants_data:
            restaurant = await db.restaurant.create({
                **restaurant_data,
                'isActive': True
            })
            restaurants.append(restaurant)
            print(f"✅ Created restaurant: {restaurant.name}")

    # 2. Create Users (Admin, Managers, Staff, Clients)
    users = []

    # Check if admin already exists, if not create one
    admin = await db.user.find_unique(where={'email': 'admin@caravane.com'})
    if not admin:
        admin = await db.user.create({
            'email': 'admin@caravane.com',
            'phone': 111111111,  # 9-digit phone number
            'firstName': 'System',
            'lastName': 'Administrator',
            'role': 'ADMIN',
            'isActive': True,
            'password': '$2b$12$KVtnpBREulpi3vjhE9SveOyGxTADCAzYOqm/5YuFL/rZy8m/5P0M6'  # hashed 'admin123'
        })
        print("✅ Created admin user")
    else:
        print("ℹ️  Admin user already exists")
    users.append(admin)

    async def find_or_create_user(email: str, data: dict):
        existing = await db.user.find_unique(where={"email": email})
        if existing:
            return existing
        return await db.user.create(data)

    # Create Managers for each restaurant
    manager_data = [
        {'firstName': 'John', 'lastName': 'Manager', 'email': 'john.manager@caravane.com', 'phone': 222222222},
        {'firstName': 'Sarah', 'lastName': 'Wilson', 'email': 'sarah.wilson@caravane.com', 'phone': 222222223},
        {'firstName': 'Mike', 'lastName': 'Johnson', 'email': 'mike.johnson@caravane.com', 'phone': 222222224},
        {'firstName': 'Lisa', 'lastName': 'Brown', 'email': 'lisa.brown@caravane.com', 'phone': 222222225}
    ]

    managers = []
    for i, manager_info in enumerate(manager_data):
        manager = await find_or_create_user(manager_info['email'], {**manager_info,
            'role': 'MANAGER',
            'isActive': True,
            'password': '$2b$12$cQ7.1vON3C2ez9pAZ8ooHOaUnG3MtHQ5/UVZUrdKX/AGwcWIK58MW',  # hashed 'manager123'
            'restaurantId': restaurants[i].id
        })
        users.append(manager)
        managers.append(manager)

    # Create Staff (Waiters, Chefs) for each restaurant
    staff_data = [
        {'firstName': 'Alice', 'lastName': 'Waiter', 'role': 'WAITER'},
        {'firstName': 'Bob', 'lastName': 'Server', 'role': 'WAITER'},
        {'firstName': 'Charlie', 'lastName': 'Chef', 'role': 'CHEF'},
        {'firstName': 'Diana', 'lastName': 'Cook', 'role': 'CHEF'}
    ]

    phone_counter = 333333330
    staff_members = []
    for restaurant in restaurants:
        for staff_info in staff_data:
            phone_counter += 1
            email = f"{staff_info['firstName'].lower()}.{staff_info['lastName'].lower()}.{restaurant.id}@caravane.com"
            staff = await find_or_create_user(email, {
                'firstName': staff_info['firstName'],
                'lastName': staff_info['lastName'],
                'email': email,
                'phone': phone_counter,
                'role': staff_info['role'],
                'isActive': True,
                'password': '$2b$12$7rOF89hoYTI/jNWv4hBhLeWfMSDE9oeRrSKSElpiZm95hRtn0Vc9y',  # hashed 'staff123'
                'restaurantId': restaurant.id
            })
            users.append(staff)
            staff_members.append(staff)

    # Create Clients
    client_data = [
        {'firstName': 'Emma', 'lastName': 'Johnson', 'email': 'emma.johnson@email.com', 'phone': 555555551},
        {'firstName': 'James', 'lastName': 'Smith', 'email': 'james.smith@email.com', 'phone': 555555552},
        {'firstName': 'Olivia', 'lastName': 'Brown', 'email': 'olivia.brown@email.com', 'phone': 555555553},
        {'firstName': 'William', 'lastName': 'Davis', 'email': 'william.davis@email.com', 'phone': 555555554},
        {'firstName': 'Sophia', 'lastName': 'Miller', 'email': 'sophia.miller@email.com', 'phone': 555555555},
        {'firstName': 'Benjamin', 'lastName': 'Wilson', 'email': 'benjamin.wilson@email.com', 'phone': 555555556},
    ]

    clients = []
    for client_info in client_data:
        client = await find_or_create_user(client_info['email'], {**client_info,
            'role': 'CLIENT',
            'isActive': True,
            'password': '$2b$12$Y2z.FHPWadE4.doQbvvFe.zdCuFi7H3dIVrViIXuqOgpxZ/14c5AS'  # hashed 'client123'
        })
        clients.append(client)
        users.append(client)

    print(f"✅ Created {len(users)} users (1 admin, {len(managers)} managers, {len(staff_members)} staff, {len(clients)} clients)")

    # 3. Create Addresses for clients
    addresses = []
    address_data = [
        {'street': '123 Oak Street', 'city': 'Downtown'},
        {'street': '456 Pine Avenue', 'city': 'Beachside'},
        {'street': '789 Maple Drive', 'city': 'Gardens'},
        {'street': '321 Cedar Lane', 'city': 'Uptown'},
        {'street': '654 Birch Road', 'city': 'Riverside'},
        {'street': '987 Elm Court', 'city': 'Hillside'},
    ]

    existing_addresses = await db.address.find_many()
    existing_user_ids = {a.userId for a in existing_addresses}

    for i, client in enumerate(clients):
        if client.id in existing_user_ids:
            address = existing_addresses[[a.userId for a in existing_addresses].index(client.id)]
        else:
            address = await db.address.create({
                'userId': client.id,
                'street': address_data[i]['street'],
                'city': address_data[i]['city'],
                'isDefault': True
            })
        addresses.append(address)

    print(f"✅ Created {len(addresses)} addresses")

    # 4. Create Tables for each restaurant
    all_tables = []
    for restaurant in restaurants:
        tables = []
        for i in range(1, 16):  # 15 tables per restaurant
            table = await db.table.create({
                'restaurantId': restaurant.id,
                'number': f'T{i:02d}',
                'capacity': random.choice([2, 4, 4, 6, 8]),  # Weighted towards 4-person tables
                'isActive': True,
                'qrCode': f'{restaurant.name.replace(" ", "")}-T{i:02d}',
            })
            tables.append(table)
            all_tables.append(table)
        print(f"✅ Created {len(tables)} tables for {restaurant.name}")

    # 5. Create Inventory Items for each restaurant
    now = datetime.now()

    inventory_items_data = [
        # Proteins
        {'name': 'Salmon Fillet', 'category': 'protein', 'unit': 'kg', 'currentStock': 25.0, 'minimumStock': 5.0, 'unitPrice': 18.0, 'supplier': 'Ocean Fresh', 'location': 'Walk-in Cooler A', 'expiryDate': now + timedelta(days=4)},
        {'name': 'Beef Tenderloin', 'category': 'protein', 'unit': 'kg', 'currentStock': 15.0, 'minimumStock': 3.0, 'unitPrice': 45.0, 'supplier': 'Prime Cuts', 'location': 'Walk-in Cooler A', 'expiryDate': now + timedelta(days=5)},
        {'name': 'Chicken Breast', 'category': 'protein', 'unit': 'kg', 'currentStock': 30.0, 'minimumStock': 8.0, 'unitPrice': 12.0, 'supplier': 'Farm Fresh', 'location': 'Walk-in Cooler A', 'expiryDate': now + timedelta(days=3)},
        {'name': 'Shrimp', 'category': 'protein', 'unit': 'kg', 'currentStock': 18.0, 'minimumStock': 4.0, 'unitPrice': 22.0, 'supplier': 'Ocean Fresh', 'location': 'Walk-in Cooler B', 'expiryDate': now + timedelta(days=2)},
        {'name': 'Lamb Rack', 'category': 'protein', 'unit': 'kg', 'currentStock': 8.0, 'minimumStock': 3.0, 'unitPrice': 38.0, 'supplier': 'Prime Cuts', 'location': 'Walk-in Cooler A', 'expiryDate': now + timedelta(days=4)},

        # Vegetables
        {'name': 'Tomatoes', 'category': 'vegetable', 'unit': 'kg', 'currentStock': 40.0, 'minimumStock': 10.0, 'unitPrice': 3.0, 'supplier': 'Garden Fresh', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=5)},
        {'name': 'Lettuce (Romaine)', 'category': 'vegetable', 'unit': 'heads', 'currentStock': 20.0, 'minimumStock': 8.0, 'unitPrice': 2.5, 'supplier': 'Garden Fresh', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=3)},
        {'name': 'Onions', 'category': 'vegetable', 'unit': 'kg', 'currentStock': 35.0, 'minimumStock': 10.0, 'unitPrice': 1.8, 'supplier': 'Garden Fresh', 'location': 'Dry Storage', 'expiryDate': now + timedelta(days=14)},
        {'name': 'Bell Peppers', 'category': 'vegetable', 'unit': 'kg', 'currentStock': 12.0, 'minimumStock': 5.0, 'unitPrice': 4.0, 'supplier': 'Garden Fresh', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=5)},
        {'name': 'Mushrooms', 'category': 'vegetable', 'unit': 'kg', 'currentStock': 6.0, 'minimumStock': 3.0, 'unitPrice': 9.0, 'supplier': 'Forest Foragers', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=3)},
        {'name': 'Eggplant', 'category': 'vegetable', 'unit': 'kg', 'currentStock': 10.0, 'minimumStock': 4.0, 'unitPrice': 3.5, 'supplier': 'Garden Fresh', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=5)},
        {'name': 'Avocado', 'category': 'vegetable', 'unit': 'pieces', 'currentStock': 25.0, 'minimumStock': 10.0, 'unitPrice': 2.0, 'supplier': 'Tropical Imports', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=3)},

        # Dairy
        {'name': 'Fresh Mozzarella', 'category': 'dairy', 'unit': 'kg', 'currentStock': 10.0, 'minimumStock': 2.0, 'unitPrice': 8.0, 'supplier': 'Artisan Cheese', 'location': 'Walk-in Cooler B', 'expiryDate': now + timedelta(days=7)},
        {'name': 'Parmesan Cheese', 'category': 'dairy', 'unit': 'kg', 'currentStock': 5.0, 'minimumStock': 2.0, 'unitPrice': 22.0, 'supplier': 'Artisan Cheese', 'location': 'Walk-in Cooler B', 'expiryDate': now + timedelta(days=30)},
        {'name': 'Heavy Cream', 'category': 'dairy', 'unit': 'liters', 'currentStock': 15.0, 'minimumStock': 5.0, 'unitPrice': 4.5, 'supplier': 'Dairy Co', 'location': 'Walk-in Cooler B', 'expiryDate': now + timedelta(days=7)},
        {'name': 'Butter', 'category': 'dairy', 'unit': 'kg', 'currentStock': 12.0, 'minimumStock': 4.0, 'unitPrice': 6.0, 'supplier': 'Dairy Co', 'location': 'Walk-in Cooler B', 'expiryDate': now + timedelta(days=14)},
        {'name': 'Eggs', 'category': 'dairy', 'unit': 'dozen', 'currentStock': 20.0, 'minimumStock': 8.0, 'unitPrice': 5.0, 'supplier': 'Farm Fresh', 'location': 'Walk-in Cooler B', 'expiryDate': now + timedelta(days=10)},

        # Grains & Pasta
        {'name': 'Pasta (Spaghetti)', 'category': 'grain', 'unit': 'kg', 'currentStock': 50.0, 'minimumStock': 15.0, 'unitPrice': 2.0, 'supplier': 'Italian Imports', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Arborio Rice', 'category': 'grain', 'unit': 'kg', 'currentStock': 20.0, 'minimumStock': 5.0, 'unitPrice': 4.5, 'supplier': 'Italian Imports', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Quinoa', 'category': 'grain', 'unit': 'kg', 'currentStock': 8.0, 'minimumStock': 3.0, 'unitPrice': 7.0, 'supplier': 'Health Foods Co', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Flour (All Purpose)', 'category': 'grain', 'unit': 'kg', 'currentStock': 30.0, 'minimumStock': 10.0, 'unitPrice': 1.5, 'supplier': 'Baking Supplies', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Bread Crumbs', 'category': 'grain', 'unit': 'kg', 'currentStock': 10.0, 'minimumStock': 3.0, 'unitPrice': 3.0, 'supplier': 'Baking Supplies', 'location': 'Dry Storage', 'expiryDate': None},

        # Spices & Herbs
        {'name': 'Basil (Fresh)', 'category': 'spice', 'unit': 'bunches', 'currentStock': 20.0, 'minimumStock': 5.0, 'unitPrice': 2.5, 'supplier': 'Herb Garden', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=3)},
        {'name': 'Mint Leaves', 'category': 'spice', 'unit': 'bunches', 'currentStock': 25.0, 'minimumStock': 8.0, 'unitPrice': 2.0, 'supplier': 'Herb Garden', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=3)},
        {'name': 'Black Pepper', 'category': 'spice', 'unit': 'kg', 'currentStock': 3.0, 'minimumStock': 1.0, 'unitPrice': 15.0, 'supplier': 'Spice Market', 'location': 'Spice Rack', 'expiryDate': None},
        {'name': 'Sea Salt', 'category': 'spice', 'unit': 'kg', 'currentStock': 5.0, 'minimumStock': 2.0, 'unitPrice': 3.0, 'supplier': 'Spice Market', 'location': 'Spice Rack', 'expiryDate': None},
        {'name': 'Garlic', 'category': 'spice', 'unit': 'kg', 'currentStock': 8.0, 'minimumStock': 3.0, 'unitPrice': 6.0, 'supplier': 'Garden Fresh', 'location': 'Dry Storage', 'expiryDate': now + timedelta(days=14)},
        {'name': 'Rosemary', 'category': 'spice', 'unit': 'bunches', 'currentStock': 10.0, 'minimumStock': 3.0, 'unitPrice': 2.5, 'supplier': 'Herb Garden', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=5)},
        {'name': 'Thyme', 'category': 'spice', 'unit': 'bunches', 'currentStock': 10.0, 'minimumStock': 3.0, 'unitPrice': 2.5, 'supplier': 'Herb Garden', 'location': 'Produce Cooler', 'expiryDate': now + timedelta(days=5)},

        # Other (oils, sauces, etc.)
        {'name': 'Olive Oil (Extra Virgin)', 'category': 'other', 'unit': 'liters', 'currentStock': 12.0, 'minimumStock': 3.0, 'unitPrice': 15.0, 'supplier': 'Mediterranean Gold', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Balsamic Vinegar', 'category': 'other', 'unit': 'liters', 'currentStock': 4.0, 'minimumStock': 1.0, 'unitPrice': 12.0, 'supplier': 'Italian Imports', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Soy Sauce', 'category': 'other', 'unit': 'liters', 'currentStock': 6.0, 'minimumStock': 2.0, 'unitPrice': 5.0, 'supplier': 'Asian Pantry', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'White Wine (Cooking)', 'category': 'other', 'unit': 'bottles', 'currentStock': 8.0, 'minimumStock': 3.0, 'unitPrice': 10.0, 'supplier': 'Wine Cellar', 'location': 'Wine Storage', 'expiryDate': None},
        {'name': 'Coconut Milk', 'category': 'other', 'unit': 'cans', 'currentStock': 15.0, 'minimumStock': 5.0, 'unitPrice': 2.5, 'supplier': 'Tropical Imports', 'location': 'Dry Storage', 'expiryDate': None},
        {'name': 'Truffle Oil', 'category': 'other', 'unit': 'bottles', 'currentStock': 3.0, 'minimumStock': 1.0, 'unitPrice': 25.0, 'supplier': 'Gourmet Imports', 'location': 'Dry Storage', 'expiryDate': None},
    ]

    all_inventory = []
    for restaurant in restaurants:
        restaurant_inventory = []
        for item_data in inventory_items_data:
            # Add some variation per restaurant
            stock_variation = random.uniform(0.7, 1.3)
            current = max(0.5, round(item_data['currentStock'] * stock_variation, 1))

            # Make some items low stock for alerts
            if random.random() < 0.15:  # 15% chance of low stock
                current = round(item_data['minimumStock'] * random.uniform(0.2, 0.8), 1)

            inventory = await db.inventory.create({
                'restaurantId': restaurant.id,
                'name': item_data['name'],
                'description': f"High quality {item_data['name'].lower()} for restaurant use",
                'category': item_data['category'],
                'unit': item_data['unit'],
                'currentStock': current,
                'minimumStock': item_data['minimumStock'],
                'unitPrice': item_data['unitPrice'],
                'supplier': item_data['supplier'],
                'location': item_data['location'],
                'expiryDate': item_data['expiryDate'],
            })
            restaurant_inventory.append(inventory)
            all_inventory.append(inventory)
        print(f"✅ Created {len(restaurant_inventory)} inventory items for {restaurant.name}")

    # 6. Create Standalone Ingredients
    ingredients_data = [
        # Proteins
        {'name': 'Salmon', 'description': 'Fresh Atlantic salmon fillet', 'category': 'Protein', 'allergenInfo': 'Fish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Beef Tenderloin', 'description': 'Premium cut beef tenderloin', 'category': 'Protein', 'allergenInfo': None, 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Chicken Breast', 'description': 'Boneless skinless chicken breast', 'category': 'Protein', 'allergenInfo': None, 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Shrimp', 'description': 'Fresh jumbo shrimp, peeled and deveined', 'category': 'Protein', 'allergenInfo': 'Shellfish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Lamb', 'description': 'Herb-crusted rack of lamb', 'category': 'Protein', 'allergenInfo': None, 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Calamari', 'description': 'Fresh squid rings', 'category': 'Protein', 'allergenInfo': 'Mollusks', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Halibut', 'description': 'Fresh Pacific halibut fillet', 'category': 'Protein', 'allergenInfo': 'Fish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Tuna', 'description': 'Sashimi-grade ahi tuna', 'category': 'Protein', 'allergenInfo': 'Fish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Pancetta', 'description': 'Italian cured pork belly', 'category': 'Protein', 'allergenInfo': None, 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Lobster', 'description': 'Fresh Maine lobster meat', 'category': 'Protein', 'allergenInfo': 'Shellfish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Mussels', 'description': 'Fresh black mussels', 'category': 'Protein', 'allergenInfo': 'Shellfish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Clams', 'description': 'Fresh littleneck clams', 'category': 'Protein', 'allergenInfo': 'Shellfish', 'isVegetarian': False, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},

        # Vegetables & Fruits
        {'name': 'Tomatoes', 'description': 'Vine-ripened Roma tomatoes', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Romaine Lettuce', 'description': 'Crisp romaine hearts', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Eggplant', 'description': 'Fresh Italian eggplant', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Avocado', 'description': 'Ripe Hass avocado', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Mushrooms', 'description': 'Wild mixed mushrooms (porcini, shiitake, oyster)', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Bell Peppers', 'description': 'Assorted color bell peppers', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Olives', 'description': 'Kalamata and green olives', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Cucumber', 'description': 'Fresh English cucumber', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Asparagus', 'description': 'Fresh green asparagus spears', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Kale', 'description': 'Fresh organic curly kale', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Lemon', 'description': 'Fresh Meyer lemons', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Lime', 'description': 'Fresh Persian limes', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Orange', 'description': 'Fresh Valencia oranges', 'category': 'Vegetable', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},

        # Dairy
        {'name': 'Mozzarella', 'description': 'Fresh buffalo mozzarella', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Parmesan', 'description': 'Aged Parmigiano-Reggiano', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Feta Cheese', 'description': 'Greek sheep milk feta', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Pecorino', 'description': 'Aged Pecorino Romano', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Heavy Cream', 'description': 'Full-fat heavy whipping cream', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Butter', 'description': 'European-style unsalted butter', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Eggs', 'description': 'Free-range large eggs', 'category': 'Dairy', 'allergenInfo': 'Eggs', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Mascarpone', 'description': 'Italian mascarpone cream cheese', 'category': 'Dairy', 'allergenInfo': 'Milk', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},

        # Grains & Starches
        {'name': 'Spaghetti', 'description': 'Italian durum wheat spaghetti', 'category': 'Grain', 'allergenInfo': 'Gluten, Wheat', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': False, 'isDairyFree': True},
        {'name': 'Arborio Rice', 'description': 'Italian short-grain Arborio rice', 'category': 'Grain', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Quinoa', 'description': 'Organic white quinoa', 'category': 'Grain', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Bread Crumbs', 'description': 'Panko breadcrumbs', 'category': 'Grain', 'allergenInfo': 'Gluten, Wheat', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': False, 'isDairyFree': True},
        {'name': 'Croutons', 'description': 'House-made garlic croutons', 'category': 'Grain', 'allergenInfo': 'Gluten, Wheat', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': False, 'isDairyFree': False},
        {'name': 'Ladyfingers', 'description': 'Italian Savoiardi biscuits', 'category': 'Grain', 'allergenInfo': 'Gluten, Wheat, Eggs', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': False, 'isDairyFree': True},

        # Herbs & Spices
        {'name': 'Basil', 'description': 'Fresh Italian sweet basil', 'category': 'Herb', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Mint', 'description': 'Fresh spearmint leaves', 'category': 'Herb', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Oregano', 'description': 'Dried Mediterranean oregano', 'category': 'Herb', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Rosemary', 'description': 'Fresh rosemary sprigs', 'category': 'Herb', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Black Pepper', 'description': 'Freshly ground Tellicherry black pepper', 'category': 'Spice', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Garlic', 'description': 'Fresh garlic cloves', 'category': 'Herb', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Cumin', 'description': 'Ground cumin seeds', 'category': 'Spice', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Curry Powder', 'description': 'Madras curry powder blend', 'category': 'Spice', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},

        # Oils, Sauces & Condiments
        {'name': 'Olive Oil', 'description': 'Extra virgin olive oil', 'category': 'Oil', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Truffle Oil', 'description': 'Black truffle-infused olive oil', 'category': 'Oil', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Sesame Oil', 'description': 'Toasted sesame oil', 'category': 'Oil', 'allergenInfo': 'Sesame', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Marinara Sauce', 'description': 'House-made tomato marinara', 'category': 'Sauce', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Wasabi', 'description': 'Fresh wasabi paste', 'category': 'Condiment', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Tahini', 'description': 'Stone-ground sesame tahini', 'category': 'Condiment', 'allergenInfo': 'Sesame', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Balsamic Vinegar', 'description': 'Aged balsamic vinegar from Modena', 'category': 'Condiment', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Coconut Milk', 'description': 'Full-fat coconut milk', 'category': 'Other', 'allergenInfo': 'Tree Nuts', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},

        # Nuts & Seeds
        {'name': 'Pine Nuts', 'description': 'Toasted Mediterranean pine nuts', 'category': 'Nut', 'allergenInfo': 'Tree Nuts', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Sesame Seeds', 'description': 'Toasted white sesame seeds', 'category': 'Nut', 'allergenInfo': 'Sesame', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Dried Cranberries', 'description': 'Sweetened dried cranberries', 'category': 'Nut', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Mixed Nuts', 'description': 'Assorted roasted nuts', 'category': 'Nut', 'allergenInfo': 'Tree Nuts, Peanuts', 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},

        # Beverages
        {'name': 'White Rum', 'description': 'Premium white rum', 'category': 'Beverage', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Bourbon', 'description': 'Kentucky straight bourbon', 'category': 'Beverage', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Tequila', 'description': 'Premium blanco tequila', 'category': 'Beverage', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Triple Sec', 'description': 'Orange liqueur', 'category': 'Beverage', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Espresso Coffee', 'description': 'Freshly brewed espresso', 'category': 'Beverage', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},

        # Baking & Dessert
        {'name': 'Dark Chocolate', 'description': '70% cacao dark chocolate', 'category': 'Baking', 'allergenInfo': 'Milk, Soy', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
        {'name': 'Vanilla Extract', 'description': 'Pure Madagascar vanilla extract', 'category': 'Baking', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Sugar', 'description': 'Granulated cane sugar', 'category': 'Baking', 'allergenInfo': None, 'isVegetarian': True, 'isVegan': True, 'isGlutenFree': True, 'isDairyFree': True},
        {'name': 'Vanilla Ice Cream', 'description': 'Premium French vanilla ice cream', 'category': 'Baking', 'allergenInfo': 'Milk, Eggs', 'isVegetarian': True, 'isVegan': False, 'isGlutenFree': True, 'isDairyFree': False},
    ]

    all_ingredients = []
    for ing_data in ingredients_data:
        ingredient = await db.ingredient.create({
            'name': ing_data['name'],
            'description': ing_data['description'],
            'allergenInfo': ing_data.get('allergenInfo'),
            'category': ing_data['category'],
            'isVegetarian': ing_data['isVegetarian'],
            'isVegan': ing_data['isVegan'],
            'isGlutenFree': ing_data['isGlutenFree'],
            'isDairyFree': ing_data['isDairyFree'],
        })
        all_ingredients.append(ingredient)

    print(f"✅ Created {len(all_ingredients)} standalone ingredients")

    # 7. Create Comprehensive Menus and Dishes
    menu_categories = [
        'Appetizers', 'Salads', 'Main Courses', 'Pasta & Risotto',
        'Seafood', 'Vegetarian', 'Desserts', 'Beverages', 'Cocktails'
    ]

    # Dishes database with categories
    dishes_database = {
        'Appetizers': [
            {'name': 'Bruschetta Trio', 'description': 'Three varieties: classic tomato basil, mushroom truffle, and avocado lime', 'price': 12.0, 'prep_time': 10},
            {'name': 'Calamari Fritti', 'description': 'Crispy fried squid rings with marinara and garlic aioli', 'price': 14.0, 'prep_time': 12},
            {'name': 'Cheese & Charcuterie Board', 'description': 'Selection of artisan cheeses, cured meats, nuts, and preserves', 'price': 18.0, 'prep_time': 8},
            {'name': 'Shrimp Cocktail', 'description': 'Jumbo shrimp with house cocktail sauce and lemon', 'price': 16.0, 'prep_time': 5},
        ],
        'Salads': [
            {'name': 'Caesar Salad', 'description': 'Crisp romaine, parmesan, croutons, and house Caesar dressing', 'price': 10.0, 'prep_time': 8},
            {'name': 'Mediterranean Bowl', 'description': 'Mixed greens, olives, feta, tomatoes, cucumber, and oregano vinaigrette', 'price': 12.0, 'prep_time': 10},
            {'name': 'Quinoa Power Salad', 'description': 'Quinoa, kale, avocado, nuts, dried cranberries, and lemon tahini dressing', 'price': 14.0, 'prep_time': 12},
        ],
        'Main Courses': [
            {'name': 'Grilled Salmon', 'description': 'Atlantic salmon with lemon herb butter and seasonal vegetables', 'price': 26.0, 'prep_time': 20},
            {'name': 'Beef Tenderloin', 'description': '8oz filet mignon with red wine reduction and garlic mashed potatoes', 'price': 34.0, 'prep_time': 25},
            {'name': 'Chicken Parmigiana', 'description': 'Breaded chicken breast with marinara, mozzarella, and spaghetti', 'price': 22.0, 'prep_time': 22},
            {'name': 'Lamb Rack', 'description': 'Herb-crusted rack of lamb with mint chimichurri and roasted vegetables', 'price': 32.0, 'prep_time': 28},
        ],
        'Pasta & Risotto': [
            {'name': 'Spaghetti Carbonara', 'description': 'Classic Roman pasta with eggs, pecorino, pancetta, and black pepper', 'price': 18.0, 'prep_time': 15},
            {'name': 'Lobster Ravioli', 'description': 'House-made ravioli filled with lobster in cream sauce', 'price': 24.0, 'prep_time': 18},
            {'name': 'Mushroom Risotto', 'description': 'Creamy Arborio rice with wild mushrooms and truffle oil', 'price': 20.0, 'prep_time': 25},
        ],
        'Seafood': [
            {'name': 'Pan-Seared Halibut', 'description': 'Fresh halibut with citrus beurre blanc and asparagus', 'price': 29.0, 'prep_time': 18},
            {'name': 'Seafood Paella', 'description': 'Traditional Spanish rice with shrimp, mussels, and clams', 'price': 26.0, 'prep_time': 35},
            {'name': 'Tuna Tataki', 'description': 'Seared ahi tuna with sesame crust and wasabi aioli', 'price': 24.0, 'prep_time': 12},
        ],
        'Vegetarian': [
            {'name': 'Eggplant Parmigiana', 'description': 'Breaded eggplant layers with marinara and mozzarella', 'price': 18.0, 'prep_time': 20},
            {'name': 'Vegetable Curry', 'description': 'Coconut curry with seasonal vegetables and basmati rice', 'price': 16.0, 'prep_time': 18},
            {'name': 'Buddha Bowl', 'description': 'Quinoa, roasted vegetables, avocado, and tahini dressing', 'price': 15.0, 'prep_time': 15},
        ],
        'Desserts': [
            {'name': 'Tiramisu', 'description': 'Classic Italian dessert with coffee-soaked ladyfingers and mascarpone', 'price': 8.0, 'prep_time': 5},
            {'name': 'Chocolate Lava Cake', 'description': 'Warm chocolate cake with molten center and vanilla ice cream', 'price': 9.0, 'prep_time': 12},
            {'name': 'Crème Brûlée', 'description': 'Vanilla custard with caramelized sugar crust', 'price': 7.0, 'prep_time': 3},
        ],
        'Beverages': [
            {'name': 'Fresh Orange Juice', 'description': 'Freshly squeezed Valencia oranges', 'price': 4.0, 'prep_time': 3},
            {'name': 'Sparkling Water', 'description': 'Premium sparkling water with lemon', 'price': 3.0, 'prep_time': 2},
            {'name': 'Iced Tea', 'description': 'House-brewed black tea served over ice', 'price': 3.5, 'prep_time': 2},
        ],
        'Cocktails': [
            {'name': 'Classic Mojito', 'description': 'White rum, mint, lime, sugar, and soda water', 'price': 10.0, 'prep_time': 5},
            {'name': 'Old Fashioned', 'description': 'Bourbon, sugar, bitters, and orange peel', 'price': 12.0, 'prep_time': 4},
            {'name': 'Margarita', 'description': 'Tequila, triple sec, lime juice, and salt rim', 'price': 11.0, 'prep_time': 4},
        ]
    }

    all_dishes = []
    restaurant_dish_map = {}  # Track dishes per restaurant for later use

    for restaurant in restaurants:
        # Create menu for restaurant
        menu = await db.menu.create({
            'restaurantId': restaurant.id,
            'name': f'{restaurant.name} Menu',
            'description': f'Signature dishes and beverages at {restaurant.name}'
        })

        # Create categories and dishes for this restaurant
        restaurant_dishes = []
        for category_name in menu_categories:
            if category_name in dishes_database:
                # Create category
                category = await db.menucategory.create({
                    'menuId': menu.id,
                    'name': category_name,
                    'description': f'{category_name} selection at {restaurant.name}',
                    'displayOrder': list(menu_categories).index(category_name)
                })

                # Create dishes for this category
                for dish_data in dishes_database[category_name]:
                    dish = await db.dish.create({
                        'categoryId': category.id,
                        'name': dish_data['name'],
                        'description': dish_data['description'],
                        'price': dish_data['price'],
                        'isAvailable': True,
                        'quantity': random.randint(50, 200),
                        'preparationTime': dish_data['prep_time'],
                        'popularity': random.uniform(3.5, 5.0)
                    })
                    restaurant_dishes.append(dish)
                    all_dishes.append(dish)

        restaurant_dish_map[restaurant.id] = restaurant_dishes
        print(f"✅ Created menu with {len(restaurant_dishes)} dishes for {restaurant.name}")

    # 8. Create DishIngredient links (dish → inventory)
    inventory_mappings = [
        ('Grilled Salmon', 'Salmon Fillet', 0.2),
        ('Pan-Seared Halibut', 'Salmon Fillet', 0.18),
        ('Seafood Paella', 'Shrimp', 0.15),
        ('Shrimp Cocktail', 'Shrimp', 0.1),
        ('Beef Tenderloin', 'Beef Tenderloin', 0.25),
        ('Chicken Parmigiana', 'Chicken Breast', 0.2),
        ('Spaghetti Carbonara', 'Pasta (Spaghetti)', 0.1),
        ('Lobster Ravioli', 'Pasta (Spaghetti)', 0.12),
        ('Eggplant Parmigiana', 'Fresh Mozzarella', 0.05),
        ('Buddha Bowl', 'Tomatoes', 0.08),
        ('Bruschetta Trio', 'Tomatoes', 0.05),
        ('Bruschetta Trio', 'Basil (Fresh)', 0.02),
        ('Cheese & Charcuterie Board', 'Fresh Mozzarella', 0.1),
        ('Classic Mojito', 'Mint Leaves', 0.01),
        ('Mushroom Risotto', 'Arborio Rice', 0.15),
        ('Mushroom Risotto', 'Mushrooms', 0.1),
        ('Caesar Salad', 'Parmesan Cheese', 0.03),
        ('Caesar Salad', 'Lettuce (Romaine)', 0.2),
        ('Lamb Rack', 'Lamb Rack', 0.3),
        ('Mediterranean Bowl', 'Tomatoes', 0.06),
        ('Quinoa Power Salad', 'Quinoa', 0.08),
        ('Tuna Tataki', 'Shrimp', 0.12),  # Using shrimp as substitute inventory
        ('Crème Brûlée', 'Heavy Cream', 0.1),
        ('Crème Brûlée', 'Eggs', 0.08),
        ('Chocolate Lava Cake', 'Butter', 0.05),
        ('Chocolate Lava Cake', 'Eggs', 0.06),
        ('Tiramisu', 'Eggs', 0.06),
        ('Vegetable Curry', 'Coconut Milk', 0.15),
    ]

    dish_inv_created = 0
    for restaurant_id, dishes in restaurant_dish_map.items():
        restaurant_inventory = [inv for inv in all_inventory if inv.restaurantId == restaurant_id]

        for dish in dishes:
            for dish_name, inventory_name, quantity in inventory_mappings:
                if dish.name == dish_name:
                    inventory_item = next((inv for inv in restaurant_inventory if inv.name == inventory_name), None)
                    if inventory_item:
                        await db.dishingredient.create({
                            'dishId': dish.id,
                            'inventoryId': inventory_item.id,
                            'quantity': quantity
                        })
                        dish_inv_created += 1

    print(f"✅ Created {dish_inv_created} dish-inventory relationships")

    # 9. Create DishIngredientLink entries (dish → standalone ingredient)
    # Build ingredient lookup by name
    ingredient_by_name = {ing.name: ing for ing in all_ingredients}

    dish_ingredient_mappings = {
        'Bruschetta Trio': ['Tomatoes', 'Basil', 'Mushrooms', 'Avocado', 'Olive Oil', 'Garlic'],
        'Calamari Fritti': ['Calamari', 'Marinara Sauce', 'Garlic', 'Lemon'],
        'Cheese & Charcuterie Board': ['Mozzarella', 'Parmesan', 'Feta Cheese', 'Mixed Nuts'],
        'Shrimp Cocktail': ['Shrimp', 'Lemon', 'Black Pepper'],
        'Caesar Salad': ['Romaine Lettuce', 'Parmesan', 'Croutons', 'Garlic', 'Lemon', 'Olive Oil', 'Eggs'],
        'Mediterranean Bowl': ['Tomatoes', 'Olives', 'Feta Cheese', 'Cucumber', 'Oregano', 'Olive Oil'],
        'Quinoa Power Salad': ['Quinoa', 'Kale', 'Avocado', 'Mixed Nuts', 'Dried Cranberries', 'Lemon', 'Tahini'],
        'Grilled Salmon': ['Salmon', 'Lemon', 'Butter', 'Rosemary', 'Asparagus'],
        'Beef Tenderloin': ['Beef Tenderloin', 'Garlic', 'Butter', 'Black Pepper', 'Rosemary'],
        'Chicken Parmigiana': ['Chicken Breast', 'Mozzarella', 'Marinara Sauce', 'Bread Crumbs', 'Eggs', 'Spaghetti'],
        'Lamb Rack': ['Lamb', 'Mint', 'Garlic', 'Rosemary', 'Olive Oil'],
        'Spaghetti Carbonara': ['Spaghetti', 'Pancetta', 'Pecorino', 'Eggs', 'Black Pepper'],
        'Lobster Ravioli': ['Lobster', 'Heavy Cream', 'Butter', 'Garlic'],
        'Mushroom Risotto': ['Arborio Rice', 'Mushrooms', 'Parmesan', 'Butter', 'Truffle Oil', 'Garlic'],
        'Pan-Seared Halibut': ['Halibut', 'Lemon', 'Butter', 'Asparagus'],
        'Seafood Paella': ['Shrimp', 'Mussels', 'Clams', 'Arborio Rice', 'Tomatoes', 'Bell Peppers', 'Garlic'],
        'Tuna Tataki': ['Tuna', 'Sesame Seeds', 'Sesame Oil', 'Wasabi'],
        'Eggplant Parmigiana': ['Eggplant', 'Mozzarella', 'Marinara Sauce', 'Bread Crumbs', 'Parmesan'],
        'Vegetable Curry': ['Coconut Milk', 'Bell Peppers', 'Curry Powder', 'Garlic', 'Tomatoes'],
        'Buddha Bowl': ['Quinoa', 'Avocado', 'Tomatoes', 'Cucumber', 'Tahini', 'Lemon'],
        'Tiramisu': ['Mascarpone', 'Ladyfingers', 'Espresso Coffee', 'Eggs', 'Sugar'],
        'Chocolate Lava Cake': ['Dark Chocolate', 'Butter', 'Eggs', 'Sugar', 'Vanilla Ice Cream'],
        'Crème Brûlée': ['Heavy Cream', 'Eggs', 'Vanilla Extract', 'Sugar'],
        'Fresh Orange Juice': ['Orange'],
        'Classic Mojito': ['White Rum', 'Mint', 'Lime', 'Sugar'],
        'Old Fashioned': ['Bourbon', 'Sugar', 'Orange'],
        'Margarita': ['Tequila', 'Triple Sec', 'Lime'],
    }

    link_created = 0
    for restaurant_id, dishes in restaurant_dish_map.items():
        for dish in dishes:
            if dish.name in dish_ingredient_mappings:
                for ing_name in dish_ingredient_mappings[dish.name]:
                    ing = ingredient_by_name.get(ing_name)
                    if ing:
                        try:
                            await db.dishingredientlink.create({
                                'dishId': dish.id,
                                'ingredientId': ing.id,
                                'quantity': f'{random.uniform(0.5, 3.0):.1f} {random.choice(["cups", "tbsp", "tsp", "oz", "pieces"])}',
                                'isOptional': random.random() < 0.1,  # 10% optional
                                'isVisible': True,
                            })
                            link_created += 1
                        except Exception:
                            pass  # Skip duplicates from unique constraint

    print(f"✅ Created {link_created} dish-ingredient links")

    # 10. Create Loyalty Cards for clients
    loyalty_cards = []
    for client in clients:
        loyalty_card = await db.loyaltycard.create({
            'userId': client.id,
            'points': random.randint(100, 500)
        })
        loyalty_cards.append(loyalty_card)

    print(f"✅ Created {len(loyalty_cards)} loyalty cards")

    # 11. Create Promotions
    promotion_data = [
        {
            'title': 'Happy Hour Special',
            'description': '50% off all cocktails from 5-7pm',
            'type': 'HAPPY_HOUR',
            'discountType': 'PERCENTAGE',
            'discountValue': 50.0,
            'startDate': now,
            'endDate': now + timedelta(days=30)
        },
        {
            'title': 'Weekend Family Deal',
            'description': '20% off orders over $50',
            'type': 'DISCOUNT',
            'discountType': 'PERCENTAGE',
            'discountValue': 20.0,
            'minOrderAmount': 50.0,
            'startDate': now,
            'endDate': now + timedelta(days=60)
        }
    ]

    promotions = []
    for restaurant in restaurants:
        for promo_data in promotion_data:
            promotion = await db.promotion.create({
                'restaurantId': restaurant.id,
                **promo_data,
                'isActive': True
            })
            promotions.append(promotion)

    print(f"✅ Created {len(promotions)} promotions")

    # 12. Create Reservations
    reservations = []
    for i, client in enumerate(clients[:3]):  # First 3 clients make reservations
        restaurant = restaurants[i % len(restaurants)]
        table = random.choice([t for t in all_tables if t.restaurantId == restaurant.id])

        reservation = await db.reservation.create({
            'userId': client.id,
            'restaurantId': restaurant.id,
            'tableId': table.id,
            'reservationStart': now + timedelta(days=1, hours=19),
            'reservationEnd': now + timedelta(days=1, hours=21),
            'status': 'CONFIRMED'
        })
        reservations.append(reservation)

    print(f"✅ Created {len(reservations)} reservations")

    # 13. Create Orders (seeded across multiple time ranges for analytics)
    orders = []
    order_counter = 1001

    # Define time ranges for orders
    time_slots = [
        # Today (within last 24h)
        *[now - timedelta(hours=h) for h in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]],
        # This week (1-6 days ago)
        *[now - timedelta(days=d, hours=random.randint(8, 20)) for d in [1, 2, 3, 4, 5, 6]],
        # This month (7-28 days ago)
        *[now - timedelta(days=d, hours=random.randint(8, 20)) for d in [7, 10, 14, 18, 21, 25, 28]],
    ]

    order_statuses = ['COMPLETED', 'COMPLETED', 'COMPLETED', 'COMPLETED', 'PREPARING', 'READY', 'CONFIRMED']

    for idx, order_time in enumerate(time_slots):
        client = clients[idx % len(clients)]
        restaurant = restaurants[idx % len(restaurants)]
        table = random.choice([t for t in all_tables if t.restaurantId == restaurant.id])

        # Get dishes for this restaurant
        restaurant_dishes = restaurant_dish_map[restaurant.id]
        num_items = random.randint(1, 4)
        selected_dishes = random.sample(restaurant_dishes, min(num_items, len(restaurant_dishes)))

        subtotal = sum(dish.price for dish in selected_dishes)
        total_amount = round(subtotal + random.uniform(2, 8), 2)

        status = random.choice(order_statuses)
        order_type = random.choice(['DINE_IN', 'TAKEAWAY', 'DELIVERY'])

        confirmed_at = order_time + timedelta(minutes=random.randint(2, 10))
        prepared_at = None
        ready_at = None
        completed_at = None

        prep_time_minutes = random.randint(5, 40)
        if status in ('COMPLETED', 'READY', 'PREPARING'):
            prepared_at = confirmed_at + timedelta(minutes=prep_time_minutes)
        if status in ('COMPLETED', 'READY'):
            ready_at = prepared_at + timedelta(minutes=random.randint(2, 8))
        if status == 'COMPLETED':
            completed_at = ready_at + timedelta(minutes=random.randint(1, 5))

        delivery_est = confirmed_at + timedelta(minutes=random.randint(20, 50))

        order = await db.order.create({
            'orderNumber': f'ORD-{order_counter}',
            'userId': client.id,
            'restaurantId': restaurant.id,
            'tableId': table.id,
            'type': order_type,
            'status': status,
            'orderTime': order_time,
            'confirmedAt': confirmed_at,
            'preparedAt': prepared_at,
            'readyAt': ready_at,
            'completedAt': completed_at,
            'estimatedDeliveryTime': delivery_est,
            'subtotal': subtotal,
            'totalAmount': total_amount,
            'paymentStatus': 'PAID' if status == 'COMPLETED' else random.choice(['PAID', 'PENDING']),
        })
        orders.append(order)
        order_counter += 1

        # Create order items
        for dish in selected_dishes:
            quantity = random.randint(1, 3)
            await db.orderitem.create({
                'orderId': order.id,
                'dishId': dish.id,
                'quantity': quantity,
                'unitPrice': dish.price,
                'totalPrice': round(dish.price * quantity, 2),
            })

    print(f"✅ Created {len(orders)} orders with order items (seeded across day/week/month)")

    # 14. Create Reviews
    reviews = []
    completed_orders = [o for o in orders if o.status == 'COMPLETED']

    for order in completed_orders[:4]:  # Reviews for first 4 completed orders
        # Get a random dish from this order
        order_items = await db.orderitem.find_many(where={'orderId': order.id})
        random_item = random.choice(order_items)

        review = await db.review.create({
            'userId': order.userId,
            'restaurantId': order.restaurantId,
            'dishId': random_item.dishId,
            'rating': random.randint(4, 5),
            'comment': random.choice([
                'Amazing food and excellent service!',
                'Delicious meal, will definitely come back.',
                'Great atmosphere and tasty dishes.',
                'Outstanding dining experience!'
            ]),
            'isVerified': True
        })
        reviews.append(review)

    print(f"✅ Created {len(reviews)} reviews")

    # 15. Create Loyalty Transactions
    loyalty_transactions = []
    for order in completed_orders:
        if order.userId:  # Only for authenticated orders
            # Find loyalty card
            loyalty_card = next((lc for lc in loyalty_cards if lc.userId == order.userId), None)
            if loyalty_card:
                points_earned = int(order.totalAmount)  # 1 point per dollar

                transaction = await db.loyaltytransaction.create({
                    'loyaltyCardId': loyalty_card.id,
                    'restaurantId': order.restaurantId,
                    'points': points_earned,
                    'type': 'EARNED',
                    'description': f'Points earned from order {order.orderNumber}'
                })
                loyalty_transactions.append(transaction)

    print(f"✅ Created {len(loyalty_transactions)} loyalty transactions")

    await db.disconnect()
    print("🎉 Database seeded successfully!")
    print(f"""
📊 Summary:
- {len(restaurants)} restaurants
- {len(users)} users (1 admin, 4 managers, 16 staff, {len(clients)} clients)
- {len(addresses)} addresses
- {len(all_tables)} tables
- {len(all_inventory)} inventory items ({len(inventory_items_data)} per restaurant)
- {len(all_ingredients)} standalone ingredients
- {len(all_dishes)} dishes across all restaurants
- {dish_inv_created} dish-inventory relationships
- {link_created} dish-ingredient links
- {len(loyalty_cards)} loyalty cards
- {len(promotions)} promotions
- {len(reservations)} reservations
- {len(orders)} orders
- {len(reviews)} reviews
- {len(loyalty_transactions)} loyalty transactions
    """)

if __name__ == '__main__':
    asyncio.run(main())
