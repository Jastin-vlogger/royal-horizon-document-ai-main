"""Loguru logger instance configured from settings."""

from loguru import logger
from src.config.settings import get_settings


def get_logger():
    """Return the configured loguru logger instance."""
    settings = get_settings()
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n",
    )
    return logger


logger = get_logger()