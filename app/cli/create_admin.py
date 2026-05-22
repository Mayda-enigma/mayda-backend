import argparse
from typing import Sequence

from app.auth.jwt import get_password_hash
from app.core.database import connect_db, disconnect_db, get_db
from app.models.user import UserRole


DEFAULT_ADMIN_EMAIL = "admin@caravane.com"
DEFAULT_ADMIN_PHONE = 1234567890
DEFAULT_ADMIN_FIRST_NAME = "Admin"
DEFAULT_ADMIN_LAST_NAME = "User"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an admin user for Caravane API")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password (min 6 chars)")
    parser.add_argument("--phone", type=int, default=DEFAULT_ADMIN_PHONE, help="Admin phone number")
    parser.add_argument("--first-name", default=DEFAULT_ADMIN_FIRST_NAME, help="Admin first name")
    parser.add_argument("--last-name", default=DEFAULT_ADMIN_LAST_NAME, help="Admin last name")
    return parser


async def create_admin_user(email: str, phone: int, first_name: str, last_name: str, password: str) -> bool:
    try:
        await connect_db()
        db = get_db()

        existing_user = await db.user.find_first(where={"OR": [{"email": email}, {"phone": phone}]})
        if existing_user:
            if existing_user.email == email:
                print(f"Error: User with email {email} already exists.")
                return False
            if existing_user.phone == phone:
                print(f"Error: User with phone {phone} already exists.")
                return False

        existing_admin = await db.user.find_first(where={"role": UserRole.ADMIN.value})
        if existing_admin:
            print(f"Error: Admin user already exists ({existing_admin.email}).")
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
        return True
    except Exception as e:
        print(f"Error creating admin user: {e}")
        return False
    finally:
        await disconnect_db()


async def run_create_admin(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if len(args.password) < 6:
        print("Error: Password must be at least 6 characters long.")
        return 1

    success = await create_admin_user(
        email=args.email,
        phone=args.phone,
        first_name=args.first_name,
        last_name=args.last_name,
        password=args.password,
    )
    return 0 if success else 1
