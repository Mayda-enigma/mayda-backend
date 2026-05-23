"""Centralized loguru configuration.

Usage:
    from app.utils.logging import logger

In development:  pretty coloured output to stderr.
In production:   structured JSON to stderr (one JSON object per line).
"""

import sys

from loguru import logger

from app.core.config import settings

# Remove loguru's default handler so we fully control the sink.
logger.remove()

if settings.ENVIRONMENT == "production":
    logger.add(
        sys.stderr,
        format="{message}",
        level="INFO",
        serialize=True,  # emit each record as a JSON object
    )
else:
    logger.add(
        sys.stderr,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        level="DEBUG",
    )

__all__ = ["logger"]
