"""Loguru logger configured from application settings."""

from loguru import logger

from src.config.settings import get_settings


def get_logger():
    """Configure and return the process logger."""

    settings = get_settings()
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    )
    return logger
