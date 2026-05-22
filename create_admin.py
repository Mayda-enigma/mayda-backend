#!/usr/bin/env python3
"""
Admin User Creation Script

This script creates an admin user for testing the Caravane API.
Run this script after setting up the database and running migrations.

Usage:
    python create_admin_simple.py

Or with custom values:
    python create_admin_simple.py --email admin@caravane.com --phone 1234567890 --password mypassword
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

from app.core.database import connect_db, disconnect_db, get_db
from app.auth.jwt import get_password_hash
from app.models.user import UserRole


async def create_admin_user(email: str, phone: int, first_name: str, last_name: str, password: str):
    """Create an admin user in the database."""
    try:
        # Connect to database
        await connect_db()
        db = get_db()
        
        # Check if user already exists
        existing_user = await db.user.find_first(
            where={
                "OR": [
                    {"email": email},
                    {"phone": phone}
                ]
            }
        )
        
        if existing_user:
            if existing_user.email == email:
                print(f"Error: User with email {email} already exists!")
                return False
            if existing_user.phone == phone:
                print(f"Error: User with phone {phone} already exists!")
                return False
        
        # Hash the password
        hashed_password = get_password_hash(password)
        
        # Create the admin user
        admin_user = await db.user.create(
            data={
                "email": email,
                "phone": phone,
                "firstName": first_name,
                "lastName": last_name,
                "password": hashed_password,
                "role": UserRole.ADMIN.value,
                "isActive": True
            }
        )
        
        print("Admin user created successfully!")
        print(f"Email: {admin_user.email}")
        print(f"Phone: {admin_user.phone}")
        print(f"Name: {admin_user.firstName} {admin_user.lastName}")
        print(f"Role: {admin_user.role}")
        print(f"User ID: {admin_user.id}")
        print("\nYou can now use these credentials to login to the API!")
        
        return True
        
    except Exception as e:
        print(f"Error creating admin user: {e}")
        return False
    finally:
        # Disconnect from database
        await disconnect_db()


async def main():
    """Main function to handle command line arguments and create admin user."""
    parser = argparse.ArgumentParser(description="Create an admin user for Caravane API")
    parser.add_argument("--email", default="admin@caravane.com", help="Admin email address")
    parser.add_argument("--phone", type=int, default=1234567890, help="Admin phone number")
    parser.add_argument("--first-name", default="Admin", help="Admin first name")
    parser.add_argument("--last-name", default="User", help="Admin last name")
    parser.add_argument("--password", default="admin123456", help="Admin password (min 6 chars)")
    
    args = parser.parse_args()
    
    # Validate password length
    if len(args.password) < 6:
        print("Error: Password must be at least 6 characters long!")
        return
    
    print("Creating admin user for Caravane API...")
    print(f"Email: {args.email}")
    print(f"Phone: {args.phone}")
    print(f"Name: {args.first_name} {args.last_name}")
    print(f"Password: {'*' * len(args.password)}")
    print()
    
    # Confirm creation
    confirm = input("Do you want to create this admin user? (y/N): ").lower().strip()
    if confirm not in ['y', 'yes']:
        print("Admin user creation cancelled.")
        return
    
    # Create the admin user
    success = await create_admin_user(
        email=args.email,
        phone=args.phone,
        first_name=args.first_name,
        last_name=args.last_name,
        password=args.password
    )
    
    if success:
        print("\nTesting Instructions:")
        print("1. Start the API server: python main.py")
        print("2. Go to: http://localhost:8000/docs")
        print("3. Use the /api/auth/login endpoint with:")
        print(f"   - Email: {args.email}")
        print(f"   - Password: {args.password}")
        print("4. Copy the access_token from the response")
        print("5. Click 'Authorize' button and enter: Bearer <your_access_token>")
        print("6. Now you can test all protected endpoints!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
