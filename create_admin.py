#!/usr/bin/env python3
"""
Admin User Creation Script

This script creates an admin user for testing the Mayda API.
Run this script after setting up the database and running migrations.

Usage:
    python create_admin_simple.py

Or with custom values:
    python create_admin_simple.py --email admin@mayda.dz --phone 1234567890 --password mypassword
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy import or_, select

from app.auth.jwt import get_password_hash
from app.core.database import connect_db, disconnect_db, get_db
from app.models.sqlalchemy_models import User, UserRole
from app.utils.logging import logger


async def create_admin_user(email: str, phone: int, first_name: str, last_name: str, password: str):
    """Create an admin user in the database."""
    try:
        # Connect to database
        await connect_db()
        db = get_db()

        # Check if user already exists
        result = await db.execute(select(User).where(or_(User.email == email, User.phone == phone)))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            if existing_user.email == email:
                logger.error("User with email {} already exists!", email)
                return False
            if existing_user.phone == phone:
                logger.error("User with phone {} already exists!", phone)
                return False

        # Hash the password
        hashed_password = get_password_hash(password)

        # Create the admin user
        admin_user = User(
            email=email,
            phone=phone,
            firstName=first_name,
            lastName=last_name,
            password=hashed_password,
            role=UserRole.ADMIN,
            isActive=True,
        )
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)

        logger.info("Admin user created successfully!")
        logger.info("Email: {}", admin_user.email)
        logger.info("Phone: {}", admin_user.phone)
        logger.info("Name: {} {}", admin_user.firstName, admin_user.lastName)
        logger.info("Role: {}", admin_user.role)
        logger.info("User ID: {}", admin_user.id)
        logger.info("You can now use these credentials to login to the API!")

        return True

    except Exception as e:
        logger.error("Error creating admin user: {}", e)
        return False
    finally:
        # Disconnect from database
        await disconnect_db()


async def main():
    """Main function to handle command line arguments and create admin user."""
    parser = argparse.ArgumentParser(description="Create an admin user for Mayda API")
    parser.add_argument("--email", default="admin@mayda.dz", help="Admin email address")
    parser.add_argument("--phone", type=int, default=1234567890, help="Admin phone number")
    parser.add_argument("--first-name", default="Admin", help="Admin first name")
    parser.add_argument("--last-name", default="User", help="Admin last name")
    parser.add_argument("--password", default="admin123456", help="Admin password (min 6 chars)")

    args = parser.parse_args()

    # Validate password length
    if len(args.password) < 6:
        logger.error("Password must be at least 6 characters long!")
        return

    logger.info("Creating admin user for Mayda API...")
    logger.info("Email: {}", args.email)
    logger.info("Phone: {}", args.phone)
    logger.info("Name: {} {}", args.first_name, args.last_name)
    logger.info("Password: {}", "*" * len(args.password))

    # Confirm creation
    confirm = input("\nDo you want to create this admin user? (y/N): ").lower().strip()
    if confirm not in ["y", "yes"]:
        logger.info("Admin user creation cancelled.")
        return

    # Create the admin user
    success = await create_admin_user(
        email=args.email,
        phone=args.phone,
        first_name=args.first_name,
        last_name=args.last_name,
        password=args.password,
    )

    if success:
        logger.info("Testing Instructions:")
        logger.info("1. Start the API server: python main.py")
        logger.info("2. Go to: http://localhost:8001/docs")
        logger.info(
            "3. Use the /api/auth/login endpoint with email={} and your password",
            args.email,
        )
        logger.info("4. Copy the access_token and use it as: Bearer <token>")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
    except Exception as e:
        logger.error("Unexpected error: {}", e)
