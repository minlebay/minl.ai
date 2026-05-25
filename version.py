"""Single source of truth for the application version."""
from __future__ import annotations
from pathlib import Path

def get_version() -> str:
    try:
        return (Path(__file__).parent / "VERSION").read_text().strip()
    except OSError:
        return "unknown"

__version__ = get_version()
