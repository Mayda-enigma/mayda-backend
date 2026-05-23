from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.auth.jwt import get_password_hash
from app.core.config import settings
from app.core.database import connect_db, disconnect_db, get_db
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.models.sqlalchemy_models import User, UserRole
from app.routes import (
    admin,
    ai,
    analytics,
    auth,
    ingredients,
    inventory,
    loyalty,
    menus,
    notifications,
    orders,
    otp,
    payments,
    promotions,
    protected,
    reservations,
    restaurants,
    reviews,
    tables,
    users,
)
from app.utils.logging import logger


async def _ensure_admin():
    """Create default admin on startup if it doesn't exist yet."""
    try:
        db = await get_db()
        result = await db.execute(select(User).where(User.email == "admin@caravane.com"))
        existing = result.scalar_one_or_none()
        if not existing:
            hashed = get_password_hash("admin123456")
            admin = User(
                email="admin@caravane.com",
                phone=1234567890,
                firstName="Admin",
                lastName="User",
                password=hashed,
                role=UserRole.ADMIN,
                isActive=True,
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            logger.info("Default admin created: admin@caravane.com / admin123456")
        else:
            logger.debug("Default admin already exists, skipping")
        await db.close()
    except Exception as e:
        logger.warning("Could not create default admin: {}", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    try:
        await connect_db()
        logger.info("Database connected successfully")
        await _ensure_admin()
    except Exception as e:
        logger.error("Failed to connect to database: {}", e)
        raise
    yield
    try:
        await disconnect_db()
        logger.info("Database disconnected successfully")
    except Exception as e:
        logger.error("Error disconnecting from database: {}", e)


app = FastAPI(
    title="Caravane Restaurant Management API",
    description="JWT Authentication with Role-Based Access Control",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.ENVIRONMENT == "development" else "Something went wrong",
        },
    )


app.include_router(auth.router, prefix="/api")
app.include_router(protected.router, prefix="/api")
app.include_router(restaurants.router, prefix="/api")
app.include_router(tables.router, prefix="/api")
app.include_router(menus.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(reservations.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(promotions.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(otp.router, prefix="/api")
app.include_router(loyalty.router, prefix="/api")
app.include_router(ingredients.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "Caravane API is running",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "message": "Welcome to Caravane Restaurant Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
