#!/usr/bin/env python3
"""
Script to inject test orders for payment API testing.
Run this script to create sample orders that you can use to test the payment functionality.
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import connect_db, get_db
from app.models.order import OrderStatus, OrderType
from app.models.user import UserRole


async def inject_test_orders():
    """Create test orders for payment API testing."""
    
    try:
        # Connect to database
        await connect_db()
        db = get_db()
        
        print("🔗 Connected to database successfully")
        
        # Get or create a test restaurant
        restaurant = await db.restaurant.find_first(
            where={"isActive": True}
        )
        
        if not restaurant:
            print("❌ No active restaurant found. Please create a restaurant first.")
            return
        
        print(f"🏪 Using restaurant: {restaurant.name} (ID: {restaurant.id})")
        
        # Get or create a test user
        test_user = await db.user.find_first(
            where={"role": UserRole.CLIENT.value}
        )
        
        if not test_user:
            # Create a test client user
            test_user = await db.user.create(
                data={
                    "email": "testclient@caravane.com",
                    "phone": 1234567899,
                    "firstName": "Test",
                    "lastName": "Client",
                    "password": "$2b$12$test.hash.for.testing.only",  # placeholder hash
                    "role": UserRole.CLIENT.value,
                    "isActive": True
                }
            )
            print(f"👤 Created test user: {test_user.email}")
        else:
            print(f"👤 Using existing user: {test_user.email} (ID: {test_user.id})")
        
        # Get dishes from the restaurant's menu
        dishes = await db.dish.find_many(
            where={
                "category": {
                    "menu": {
                        "restaurantId": restaurant.id
                    }
                },
                "isAvailable": True
            },
            take=3  # Get up to 3 dishes
        )
        
        if not dishes:
            print("❌ No available dishes found. Please add dishes to the restaurant menu first.")
            return
        
        print(f"🍽️ Found {len(dishes)} available dishes")
        
        # Create test orders
        test_orders = [
            {
                "type": OrderType.DINE_IN,
                "subtotal": 2500.0,
                "total": 2500.0,
                "notes": "Test order for payment API - Dine In"
            },
            {
                "type": OrderType.TAKEAWAY,
                "subtotal": 1800.0,
                "total": 1800.0,
                "notes": "Test order for payment API - Takeaway"
            },
            {
                "type": OrderType.DELIVERY,
                "subtotal": 3200.0,
                "deliveryFee": 300.0,
                "total": 3500.0,
                "notes": "Test order for payment API - Delivery"
            }
        ]
        
        created_orders = []
        
        for i, order_data in enumerate(test_orders):
            # Generate unique order number
            order_number = f"TEST{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
            
            # Create the order
            order = await db.order.create(
                data={
                    "orderNumber": order_number,
                    "userId": test_user.id,
                    "restaurantId": restaurant.id,
                    "type": order_data["type"].value,
                    "status": OrderStatus.CONFIRMED.value,
                    "subtotal": order_data["subtotal"],
                    "deliveryFee": order_data.get("deliveryFee", 0.0),
                    "discount": 0.0,
                    "totalAmount": order_data["total"],
                    "paymentStatus": "PENDING",
                    "notes": order_data["notes"],
                    "confirmedAt": datetime.now()
                }
            )
            
            # Add order items
            for j, dish in enumerate(dishes[:2]):  # Add 2 dishes per order
                quantity = j + 1  # 1 or 2 quantity
                unit_price = dish.price
                total_price = unit_price * quantity
                
                await db.orderitem.create(
                    data={
                        "orderId": order.id,
                        "dishId": dish.id,
                        "quantity": quantity,
                        "unitPrice": unit_price,
                        "totalPrice": total_price,
                        "notes": f"Test item {j+1}"
                    }
                )
            
            created_orders.append(order)
            print(f"✅ Created test order: {order.orderNumber} (ID: {order.id}) - {order_data['type'].value} - ${order_data['total']}")
        
        print(f"\n🎉 Successfully created {len(created_orders)} test orders!")
        print("\n📝 Test Order Details:")
        print("=" * 60)
        
        for order in created_orders:
            print(f"Order Number: {order.orderNumber}")
            print(f"Order ID: {order.id}")
            print(f"Type: {order.type}")
            print(f"Total Amount: ${order.totalAmount}")
            print(f"Status: {order.status}")
            print(f"Payment Status: {order.paymentStatus}")
            print("-" * 40)
        
        print("\n🧪 How to test the Payment API:")
        print("1. Start the FastAPI server: uvicorn main:app --reload")
        print("2. Go to http://localhost:8000/docs")
        print("3. Login with the test user credentials or create a new user")
        print("4. Use the order IDs above to test payment endpoints:")
        print("   - POST /api/payments/initiate (with orderId)")
        print("   - GET /api/payments/show/{orderNumber}")
        print("   - GET /api/payments/receipt/{orderNumber}")
        
        print(f"\n👤 Test User Credentials:")
        print(f"Email: {test_user.email}")
        print(f"User ID: {test_user.id}")
        print("Password: (use your auth system to create a proper password)")
        
    except Exception as e:
        print(f"❌ Error creating test orders: {e}")
        import traceback
        traceback.print_exc()


async def clean_test_orders():
    """Clean up test orders (optional)."""
    try:
        await connect_db()
        db = get_db()
        
        # Delete test orders (those with orderNumber starting with "TEST")
        deleted_orders = await db.order.delete_many(
            where={
                "orderNumber": {
                    "startswith": "TEST"
                }
            }
        )
        
        print(f"🧹 Cleaned up {deleted_orders} test orders")
        
    except Exception as e:
        print(f"❌ Error cleaning test orders: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        print("🧹 Cleaning up test orders...")
        asyncio.run(clean_test_orders())
    else:
        print("🚀 Injecting test orders for payment API testing...")
        asyncio.run(inject_test_orders())
        print("\n💡 To clean up test orders later, run: python inject_test_orders.py clean")
