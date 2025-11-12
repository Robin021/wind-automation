from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import AppConfig


def setup_logging(config: AppConfig) -> None:
    """Configure root logger for both console and file outputs."""
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers = []

    file_handler = RotatingFileHandler(
        config.paths.log_file,
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)
