from enum import Enum


class UserRole(str, Enum):
    """User roles enum matching Prisma schema."""
    CLIENT = "CLIENT"
    WAITER = "WAITER"
    CHEF = "CHEF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
