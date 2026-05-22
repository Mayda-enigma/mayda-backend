from prisma import Prisma
from typing import Optional

# Global database connection
db: Optional[Prisma] = None


async def connect_db():
    """Connect to the database."""
    global db
    if db is None:
        db = Prisma()
        await db.connect()


async def disconnect_db():
    """Disconnect from the database."""
    global db
    if db is not None:
        await db.disconnect()


def get_db() -> Prisma:
    """Get the database connection."""
    global db
    if db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db
