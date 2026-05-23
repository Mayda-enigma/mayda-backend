# Mayda Backend — Restaurant Management API

FastAPI + Prisma + PostgreSQL backend for the Mayda restaurant management platform.

## Tech Stack

- **Framework:** FastAPI (Python 3.10+)
- **Database:** PostgreSQL 15 with Prisma ORM
- **Auth:** JWT (python-jose) + 2FA SMS (Twilio)
- **Validation:** Pydantic v2
- **Payments:** Guidini Pay
- **Infrastructure:** Docker Compose, Nginx

## Quick Start (Local)

```bash
# Clone
git clone https://github.com/Mayda-enigma/mayda-backend.git
cd mayda-backend

# Python env
python -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Prisma client & migrations
prisma generate
prisma migrate dev

# Run
uvicorn main:app --reload --port 8001
```

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up -d
```

The API is at `http://localhost:8001/docs` (Swagger UI).

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `SECRET_KEY` | Yes | — | JWT signing secret |
| `ALGORITHM` | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token TTL |
| `TWILIO_ACCOUNT_SID` | For 2FA | — | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | For 2FA | — | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | For 2FA | — | SMS sender number |
| `GUIDINI_APP_KEY` | For payments | — | Guidini Pay app key |
| `GUIDINI_API_KEY` | For payments | — | Guidini Pay API key |
| `ENVIRONMENT` | No | `development` | `development` / `production` |

Copy `.env.example` to `.env` and fill in the values.

## Database

```bash
# Generate Prisma client (after schema changes)
prisma generate

# Create a new migration
prisma migrate dev --name <name>

# Apply migrations in production
prisma migrate deploy
```

## First-time Setup

After migrations are applied and the server is running, create the initial admin user with the CLI:

```bash
python -m app.cli create-admin \
  --email admin@caravane.com \
  --phone 1234567890 \
  --password <secure-password>
```

Options:

| Flag | Required | Default | Description |
|---|---|---|---|
| `--email` | Yes | — | Admin email address |
| `--phone` | Yes | — | Admin phone number |
| `--password` | Yes | — | Password (min 6 chars) |
| `--first-name` | No | `Admin` | First name |
| `--last-name` | No | `User` | Last name |

The command refuses to run if a user with the same email or phone already exists.
No admin is created automatically on startup — creation is always explicit.
## Role-Based Access Control (RBAC)

RBAC is enforced exclusively through **FastAPI `Depends` functions** declared in `app/middleware/roles.py`. Use these dependencies in route signatures — never implement role checks inline or via decorators.

| Dependency | Allowed roles |
|---|---|
| `get_current_user` | Any authenticated user |
| `get_current_user_optional` | Any user (unauthenticated returns `None`) |
| `get_current_staff_user` | `WAITER`, `CHEF`, `MANAGER`, `ADMIN` |
| `get_current_manager_or_admin` | `MANAGER`, `ADMIN` |
| `get_current_admin_user` | `ADMIN` only |

Example:

```python
from app.middleware.roles import get_current_admin_user

@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    current_user=Depends(get_current_admin_user),
    db=Depends(get_db_session),
):
    ...
```

## Project Structure

```
├── app/
│   ├── core/           # Config, database, dependencies
│   ├── models/         # Pydantic models / schemas
│   ├── routes/         # API route handlers
│   ├── auth/           # JWT & authentication logic
│   └── services/       # Business logic
├── prisma/
│   ├── schema.prisma   # Database schema
│   └── migrations/     # Migration history
├── main.py             # FastAPI application entrypoint
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```
