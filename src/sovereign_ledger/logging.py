"""Structured logging setup."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure JSON-structured logging for the application."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
