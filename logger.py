"""Logging configuration shared by DriftMind runtime modules."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging without adding duplicate Lambda handlers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        logging.basicConfig(level=level, format=_LOG_FORMAT)
        return

    formatter = logging.Formatter(_LOG_FORMAT)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def get_logger(name: str) -> logging.Logger:
    """Return a named application logger."""
    return logging.getLogger(name)
