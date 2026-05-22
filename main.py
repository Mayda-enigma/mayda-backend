from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import uvicorn

from app.core.config import settings
from app.core.database import connect_db, disconnect_db, get_db
from app.routes import auth, protected, restaurants, tables, menus, orders, reservations, reviews, promotions, payments, otp
from app.auth.jwt import get_password_hash
from app.models.user import UserRole


# Create FastAPI app
app = FastAPI(
    title="Caravane Restaurant Management API",
    description="JWT Authentication with Role-Based Access Control",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for better error responses."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.ENVIRONMENT == "development" else "Something went wrong"
        }
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    try:
        await connect_db()
        print("Database connected successfully")
        
        # Check if admin user exists, create one if not
        await ensure_admin_user_exists()
        
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        raise


async def ensure_admin_user_exists():
    """Check if an admin user exists, create one if not."""
    try:
        db = get_db()
        
        # Check if any admin user exists
        admin_user = await db.user.find_first(
            where={"role": UserRole.ADMIN.value}
        )
        
        if admin_user:
            print(f"Admin user already exists: {admin_user.email}")
            return
        
        # Create default admin user
        hashed_password = get_password_hash("admin123456")
        
        admin_user = await db.user.create(
            data={
                "email": "admin@caravane.com",
                "phone": 1234567890,
                "firstName": "Admin",
                "lastName": "User",
                "password": hashed_password,
                "role": UserRole.ADMIN.value,
                "isActive": True
            }
        )
        
        print("Default admin user created successfully!")
        print(f"Email: {admin_user.email}")
        print(f"Password: admin123456")
        print("Please change the default credentials after first login!")
        
    except Exception as e:
        print(f"Error creating admin user: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown."""
    try:
        await disconnect_db()
        print("Database disconnected successfully")
    except Exception as e:
        print(f"Error disconnecting from database: {e}")


# Include routers
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


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "Caravane API is running",
        "version": "1.0.0"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to Caravane Restaurant Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
