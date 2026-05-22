import asyncio
import json
from prisma import Prisma
from datetime import datetime, timedelta
import random

async def main():
    db = Prisma()
    await db.connect()
    
    print("🚀 Starting database seeding...")

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
        print(f"✅ Created admin user")
    else:
        print(f"ℹ️  Admin user already exists")
    users.append(admin)
    
    # Create Managers for each restaurant
    manager_data = [
        {'firstName': 'John', 'lastName': 'Manager', 'email': 'john.manager@caravane.com', 'phone': 222222222},
        {'firstName': 'Sarah', 'lastName': 'Wilson', 'email': 'sarah.wilson@caravane.com', 'phone': 222222223},
        {'firstName': 'Mike', 'lastName': 'Johnson', 'email': 'mike.johnson@caravane.com', 'phone': 222222224},
        {'firstName': 'Lisa', 'lastName': 'Brown', 'email': 'lisa.brown@caravane.com', 'phone': 222222225}
    ]
    
    managers = []
    for i, manager_info in enumerate(manager_data):
        manager = await db.user.create({
            **manager_info,
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
            staff = await db.user.create({
                'firstName': staff_info['firstName'],
                'lastName': staff_info['lastName'],
                'email': f"{staff_info['firstName'].lower()}.{staff_info['lastName'].lower()}.{restaurant.id}@caravane.com",
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
        client = await db.user.create({
            **client_info,
            'role': 'CLIENT',
            'isActive': True,
            'password': '$2b$12$Y2z.FHPWadE4.doQbvvFe.zdCuFi7H3dIVrViIXuqOgpxZ/14c5AS'  # hashed 'client123'
        })
        clients.append(client)
        users.append(client)
    
    print(f"✅ Created {len(users)} users (1 admin, 4 managers, 16 staff, {len(clients)} clients)")

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
    
    for i, client in enumerate(clients):
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
    inventory_items_data = [
        {'itemName': 'Salmon Fillet', 'unit': 'kg', 'currentStock': 25, 'minStock': 5, 'unitCost': 18.0, 'supplier': 'Ocean Fresh'},
        {'itemName': 'Beef Tenderloin', 'unit': 'kg', 'currentStock': 15, 'minStock': 3, 'unitCost': 45.0, 'supplier': 'Prime Cuts'},
        {'itemName': 'Chicken Breast', 'unit': 'kg', 'currentStock': 30, 'minStock': 8, 'unitCost': 12.0, 'supplier': 'Farm Fresh'},
        {'itemName': 'Fresh Mozzarella', 'unit': 'kg', 'currentStock': 10, 'minStock': 2, 'unitCost': 8.0, 'supplier': 'Artisan Cheese'},
        {'itemName': 'Tomatoes', 'unit': 'kg', 'currentStock': 40, 'minStock': 10, 'unitCost': 3.0, 'supplier': 'Garden Fresh'},
        {'itemName': 'Basil', 'unit': 'bunch', 'currentStock': 20, 'minStock': 5, 'unitCost': 2.5, 'supplier': 'Herb Garden'},
        {'itemName': 'Olive Oil', 'unit': 'liter', 'currentStock': 12, 'minStock': 3, 'unitCost': 15.0, 'supplier': 'Mediterranean Gold'},
        {'itemName': 'Pasta', 'unit': 'kg', 'currentStock': 50, 'minStock': 15, 'unitCost': 2.0, 'supplier': 'Italian Imports'},
        {'itemName': 'Mint Leaves', 'unit': 'bunch', 'currentStock': 25, 'minStock': 8, 'unitCost': 2.0, 'supplier': 'Fresh Herbs'},
        {'itemName': 'Shrimp', 'unit': 'kg', 'currentStock': 18, 'minStock': 4, 'unitCost': 22.0, 'supplier': 'Ocean Fresh'},
    ]
    
    all_inventory = []
    for restaurant in restaurants:
        restaurant_inventory = []
        for item_data in inventory_items_data:
            inventory = await db.inventory.create({
                'restaurantId': restaurant.id,
                'itemName': item_data['itemName'],
                'description': f"High quality {item_data['itemName'].lower()} for restaurant use",
                'unit': item_data['unit'],
                'currentStock': item_data['currentStock'] + random.randint(-5, 10),
                'minStock': item_data['minStock'],
                'unitCost': item_data['unitCost'],
                'supplier': item_data['supplier']
            })
            restaurant_inventory.append(inventory)
            all_inventory.append(inventory)
        print(f"✅ Created {len(restaurant_inventory)} inventory items for {restaurant.name}")

    # 6. Create Comprehensive Menus and Dishes
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

    # 7. Create Ingredients (link dishes to inventory)
    ingredient_mappings = [
        # Salmon dishes use salmon inventory
        ('Grilled Salmon', 'Salmon Fillet', 0.2),
        ('Pan-Seared Halibut', 'Salmon Fillet', 0.18),  # Using salmon as substitute
        ('Seafood Paella', 'Shrimp', 0.15),
        ('Shrimp Cocktail', 'Shrimp', 0.1),
        
        # Meat dishes
        ('Beef Tenderloin', 'Beef Tenderloin', 0.25),
        ('Chicken Parmigiana', 'Chicken Breast', 0.2),
        
        # Pasta dishes
        ('Spaghetti Carbonara', 'Pasta', 0.1),
        ('Lobster Ravioli', 'Pasta', 0.12),
        
        # Vegetarian dishes
        ('Eggplant Parmigiana', 'Fresh Mozzarella', 0.05),
        ('Buddha Bowl', 'Tomatoes', 0.08),
        
        # Appetizers
        ('Bruschetta Trio', 'Tomatoes', 0.05),
        ('Bruschetta Trio', 'Basil', 0.02),
        ('Cheese & Charcuterie Board', 'Fresh Mozzarella', 0.1),
        
        # Cocktails
        ('Classic Mojito', 'Mint Leaves', 0.01),
    ]
    
    ingredients_created = 0
    for restaurant_id, dishes in restaurant_dish_map.items():
        # Get inventory for this restaurant
        restaurant_inventory = [inv for inv in all_inventory if inv.restaurantId == restaurant_id]
        
        for dish in dishes:
            for dish_name, inventory_name, quantity in ingredient_mappings:
                if dish.name == dish_name:
                    # Find the inventory item
                    inventory_item = next((inv for inv in restaurant_inventory if inv.itemName == inventory_name), None)
                    if inventory_item:
                        ingredient = await db.ingredient.create({
                            'dishId': dish.id,
                            'InventoryId': inventory_item.id,
                            'quantity': quantity
                        })
                        ingredients_created += 1
    
    print(f"✅ Created {ingredients_created} ingredient relationships")

    # 8. Create Loyalty Cards for clients
    loyalty_cards = []
    for client in clients:
        loyalty_card = await db.loyaltycard.create({
            'userId': client.id,
            'points': random.randint(100, 500)
        })
        loyalty_cards.append(loyalty_card)
    
    print(f"✅ Created {len(loyalty_cards)} loyalty cards")

    # 9. Create Promotions
    promotion_data = [
        {
            'title': 'Happy Hour Special',
            'description': '50% off all cocktails from 5-7pm',
            'type': 'HAPPY_HOUR',
            'discountType': 'PERCENTAGE',
            'discountValue': 50.0,
            'startDate': datetime.now(),
            'endDate': datetime.now() + timedelta(days=30)
        },
        {
            'title': 'Weekend Family Deal',
            'description': '20% off orders over $50',
            'type': 'DISCOUNT',
            'discountType': 'PERCENTAGE',
            'discountValue': 20.0,
            'minOrderAmount': 50.0,
            'startDate': datetime.now(),
            'endDate': datetime.now() + timedelta(days=60)
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

    # 10. Create Reservations
    reservations = []
    for i, client in enumerate(clients[:3]):  # First 3 clients make reservations
        restaurant = restaurants[i % len(restaurants)]
        table = random.choice([t for t in all_tables if t.restaurantId == restaurant.id])
        
        reservation = await db.reservation.create({
            'userId': client.id,
            'restaurantId': restaurant.id,
            'tableId': table.id,
            'reservationStart': datetime.now() + timedelta(days=1, hours=19),
            'reservationEnd': datetime.now() + timedelta(days=1, hours=21),
            'status': 'CONFIRMED'
        })
        reservations.append(reservation)
    
    print(f"✅ Created {len(reservations)} reservations")

    # 11. Create Orders
    orders = []
    order_counter = 1001
    
    for i, client in enumerate(clients):
        restaurant = restaurants[i % len(restaurants)]
        table = random.choice([t for t in all_tables if t.restaurantId == restaurant.id])
        
        # Get dishes for this restaurant
        restaurant_dishes = restaurant_dish_map[restaurant.id]
        selected_dishes = random.sample(restaurant_dishes, min(3, len(restaurant_dishes)))
        
        subtotal = sum(dish.price for dish in selected_dishes)
        total_amount = subtotal + random.uniform(2, 5)  # Add some delivery fee/tax
        
        order = await db.order.create({
            'orderNumber': f'ORD-{order_counter}',
            'userId': client.id,
            'restaurantId': restaurant.id,
            'tableId': table.id,
            'type': random.choice(['DINE_IN', 'TAKEAWAY', 'DELIVERY']),
            'status': random.choice(['COMPLETED', 'COMPLETED', 'PREPARING']),  # Weighted towards completed
            'subtotal': subtotal,
            'totalAmount': total_amount,
            'paymentStatus': 'PAID'
        })
        orders.append(order)
        order_counter += 1
        
        # Create order items
        for dish in selected_dishes:
            await db.orderitem.create({
                'orderId': order.id,
                'dishId': dish.id,
                'quantity': 1,
                'unitPrice': dish.price,
                'totalPrice': dish.price
            })
    
    print(f"✅ Created {len(orders)} orders with order items")

    # 12. Create Reviews
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

    # 13. Create Loyalty Transactions
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
- {len(all_inventory)} inventory items
- {len(all_dishes)} dishes across all restaurants
- {ingredients_created} ingredient relationships
- {len(loyalty_cards)} loyalty cards
- {len(promotions)} promotions
- {len(reservations)} reservations
- {len(orders)} orders
- {len(reviews)} reviews
- {len(loyalty_transactions)} loyalty transactions
    """)

if __name__ == '__main__':
    asyncio.run(main())
