"""Centralized logging for minl.ai. Call setup() once at startup."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_FILE = Path.home() / ".config" / "minlai" / "minlai.log"
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB per file
_BACKUP_COUNT = 1


def setup() -> None:
    """Initialize rotating file logger. Safe to call multiple times."""
    if logging.getLogger().handlers:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)-16s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)
