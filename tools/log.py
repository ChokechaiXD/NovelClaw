"""Structured logging for NovelClaw tools.

Usage:
    from tools.log import logger
    logger.info("Processing chapter {ch}", ch=42)
    logger.error("LLM call failed", exc_info=e, retries=3)
"""
import logging
import os
import sys
from pathlib import Path


def setup_logger(name: str = "novelclaw", log_file: str | None = None) -> logging.Logger:
    """Configure and return a structured logger.

    Reads LOG_LEVEL and LOG_FILE from environment (with .env fallback).
    Logs to stderr by default, optionally to a file.

    Args:
        name: Logger name (default: "novelclaw")
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Format: JSON-like structured output
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Always log to stderr
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setFormatter(formatter)
    logger.addHandler(stderr)

    # Optionally log to file
    log_path = log_file or os.environ.get("LOG_FILE")
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


# Default module-level logger (importable directly)
logger = setup_logger()
