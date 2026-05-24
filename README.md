# mayda-backend

> REST API for the Mayda restaurant platform — powering menus, orders, inventory, reviews, and loyalty.

## Overview

`mayda-backend` is a FastAPI-based REST API that serves as the backbone of the Mayda ecosystem. It manages multi-restaurant operations including menu browsing, order processing, user authentication, inventory tracking, customer reviews, and loyalty programs. PostgreSQL with Alembic migrations ensures data consistency across deployments.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python) |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Auth | JWT-based |
| Validation | Pydantic v2 |
| Testing | pytest (107 tests) |

## Project Structure

```
mayda-backend/
├── app/
│   ├── models/           # SQLAlchemy ORM models
│   ├── routes/           # API endpoint routers
│   ├── services/         # Business logic layer
│   ├── schemas/          # Pydantic request/response schemas
│   ├── auth/             # JWT authentication
│   └── main.py           # FastAPI app entrypoint
├── alembic/
│   ├── versions/         # Database migrations
│   └── env.py
├── tests/                # pytest suite
├── Dockerfile
└── requirements.txt
```

## API Modules

| Module | Description |
|---|---|
| **Restaurants** | CRUD, search, multi-brand management |
| **Menus** | Categories, menu items, modifiers |
| **Orders** | Creation, status tracking, history |
| **Users** | Registration, profiles, roles (customer/manager/admin) |
| **Inventory** | Stock management, cost tracking, alerts |
| **Reviews** | Ratings, feedback, moderation |
| **Loyalty** | Points, rewards, transaction history |
| **Orders** | Pricing, discounts, tax calculation |
| **Ingredients** | Dish composition, dietary info |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest
```

## API Documentation

When running, interactive docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Database Migrations

Migrations are managed with Alembic and auto-applied on container startup:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```
