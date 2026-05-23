"""Admin user creation logic for the CLI."""

from sqlalchemy import or_, select

from app.auth.jwt import get_password_hash
from app.core.database import connect_db, disconnect_db, get_db
from app.models.sqlalchemy_models import User, UserRole


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

        result = await db.execute(select(User).where(or_(User.email == email, User.phone == phone)))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            if existing_user.email == email:
                print(f"Error: User with email {email} already exists.")
            else:
                print(f"Error: User with phone {phone} already exists.")
            return False

        hashed_password = get_password_hash(password)

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

        print("Admin user created successfully!")
        print(f"Email: {admin_user.email}")
        print(f"Phone: {admin_user.phone}")
        print(f"Name: {admin_user.firstName} {admin_user.lastName}")
        print(f"Role: {admin_user.role}")
        print(f"User ID: {admin_user.id}")
        return True

    finally:
        await disconnect_db()
