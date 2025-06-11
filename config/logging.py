"""
Logging configuration for AgroBot Raspberry Pi application
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

from config.settings import get_settings


def setup_logging(log_file: Optional[str] = None, log_level: Optional[str] = None):
    """
    Configure logging for the application
    
    Args:
        log_file: Path to log file (overrides settings)
        log_level: Log level (overrides settings)
    """
    settings = get_settings()
    
    # Use provided parameters or fall back to settings
    log_level = log_level or settings.LOG_LEVEL
    log_file = log_file or settings.LOG_FILE
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log file specified)
    if log_file:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=settings.LOG_MAX_SIZE,
                backupCount=settings.LOG_BACKUP_COUNT
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file handler: {e}")
    
    # Set specific logger levels
    configure_third_party_loggers(numeric_level)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {log_level}, File: {log_file}")


def configure_third_party_loggers(base_level: int):
    """Configure logging levels for third-party libraries"""
    
    # MAVLink library can be very verbose
    logging.getLogger('pymavlink').setLevel(max(base_level, logging.WARNING))
    
    # FastAPI/Uvicorn loggers
    logging.getLogger('uvicorn').setLevel(base_level)
    logging.getLogger('uvicorn.access').setLevel(max(base_level, logging.INFO))
    logging.getLogger('fastapi').setLevel(base_level)
    
    # HTTP requests
    logging.getLogger('urllib3').setLevel(max(base_level, logging.WARNING))
    logging.getLogger('requests').setLevel(max(base_level, logging.WARNING))
    
    # Asyncio
    if base_level > logging.DEBUG:
        logging.getLogger('asyncio').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        return logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_function_call(func):
    """Decorator to log function calls (for debugging)"""
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised exception: {e}")
            raise
    return wrapper


async def log_async_function_call(func):
    """Decorator to log async function calls (for debugging)"""
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"Calling async {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Async {func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"Async {func.__name__} raised exception: {e}")
            raise
    return wrapper


def create_performance_logger(name: str) -> logging.Logger:
    """
    Create a separate logger for performance metrics
    
    Args:
        name: Logger name
        
    Returns:
        Performance logger instance
    """
    perf_logger = logging.getLogger(f"performance.{name}")
    
    # Create separate handler for performance logs
    settings = get_settings()
    if settings.LOG_FILE:
        log_dir = Path(settings.LOG_FILE).parent
        perf_log_file = log_dir / "performance.log"
        
        try:
            perf_handler = logging.handlers.RotatingFileHandler(
                perf_log_file,
                maxBytes=settings.LOG_MAX_SIZE // 4,  # Smaller file for performance logs
                backupCount=3
            )
            perf_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S.%f'
            )
            perf_handler.setFormatter(perf_formatter)
            perf_logger.addHandler(perf_handler)
            perf_logger.setLevel(logging.INFO)
        except Exception as e:
            print(f"Warning: Could not create performance log handler: {e}")
    
    return perf_logger