"""Centralized logging for minl.ai. Call setup() once at startup."""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

LOG_FILE = Path.home() / ".config" / "minlai" / "minlai.log"
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB per file
_BACKUP_COUNT = 1

# Third-party SDK loggers emit full HTTP request bodies (including base64
# screenshots and clipboard text) at DEBUG level — suppress them.
_NOISY_LOGGERS = (
    "anthropic", "httpcore", "httpx",
    "google", "google.auth", "google.genai",
    "urllib3", "charset_normalizer",
)


def setup() -> None:
    """Initialize rotating file logger. Safe to call multiple times."""
    if logging.getLogger().handlers:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # H1 fix: create log file with owner-only permissions (0o600)
    old_umask = os.umask(0o177)
    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
    finally:
        os.umask(old_umask)

    # Also fix permissions on an existing log file from a previous run
    try:
        LOG_FILE.chmod(0o600)
    except OSError:
        pass

    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)-16s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)

    # H2 fix: suppress noisy SDK loggers so request bodies aren't persisted
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)
