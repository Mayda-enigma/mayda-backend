#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
