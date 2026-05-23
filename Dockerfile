# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/appuser \
    XDG_CACHE_HOME=/home/appuser/.cache \
    PRISMA_HOME_DIR=/home/appuser/.prisma \
    PRISMA_BINARY_CACHE_DIR=/home/appuser/.cache/prisma-python/binaries \
    PRISMA_NODEENV_CACHE_DIR=/home/appuser/.cache/prisma-python/nodeenv

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Prisma CLI
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install Prisma CLI globally
RUN npm install -g prisma

# Generate Prisma client
RUN prisma generate

# Create non-root user for security
RUN addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --home /home/appuser appuser

# Change ownership of app directory
RUN chown -R appuser:appgroup /app

RUN mkdir -p /home/appuser/.cache/prisma-python/binaries \
    /home/appuser/.cache/prisma-python/nodeenv \
    /home/appuser/.prisma \
    && chown -R appuser:appgroup /home/appuser /app
# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/docs || exit 1

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
