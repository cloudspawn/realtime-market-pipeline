"""
Structured logging configuration using structlog.

Produces JSON logs in production, pretty logs in development.
"""

import logging
import sys

import structlog


def setup_logging(json_format: bool = True, level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        json_format: If True, output JSON logs. If False, pretty console logs.
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
    
    Usage:
        from src.common.logging import setup_logging, get_logger
        
        setup_logging(json_format=True)
        logger = get_logger(__name__)
        logger.info("message", key="value")
    """
    # Set base logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Shared processors for all environments
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    if json_format:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Usually __name__ of the calling module.
    
    Returns:
        Configured structlog logger.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("starting", component="producer")
        logger.error("failed", error=str(e), symbol="btcusdt")
    """
    return structlog.get_logger(name)