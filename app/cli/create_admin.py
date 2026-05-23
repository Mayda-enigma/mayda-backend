"""Admin user creation logic for the CLI."""

import asyncio

from app.core.database import connect_db, disconnect_db, get_db
from app.auth.jwt import get_password_hash
from app.models.user import UserRole


async def create_admin_user(
    email: str,
    phone: int,
    first_name: str,
    last_name: str,
    password: str,
) -> bool:
    """Create an admin user in the database. Returns False if user already exists."""
    await connect_db()
    try:
        db = get_db()

        existing_user = await db.user.find_first(
            where={
                "OR": [
                    {"email": email},
                    {"phone": phone},
                ]
            }
        )

        if existing_user:
            if existing_user.email == email:
                print(f"Error: User with email {email} already exists.")
            else:
                print(f"Error: User with phone {phone} already exists.")
            return False

        hashed_password = get_password_hash(password)

        admin_user = await db.user.create(
            data={
                "email": email,
                "phone": phone,
                "firstName": first_name,
                "lastName": last_name,
                "password": hashed_password,
                "role": UserRole.ADMIN.value,
                "isActive": True,
            }
        )

        print("Admin user created successfully!")
        print(f"Email: {admin_user.email}")
        print(f"Phone: {admin_user.phone}")
        print(f"Name: {admin_user.firstName} {admin_user.lastName}")
        print(f"Role: {admin_user.role}")
        print(f"User ID: {admin_user.id}")
        return True

    finally:
        await disconnect_db()
