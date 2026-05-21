"""Screen region capture and clipboard/selection reading."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import os
from typing import Optional


TOOL_FLAMESHOT = "flameshot"
TOOL_SPECTACLE = "spectacle"


def capture_screenshot(tool: str = TOOL_FLAMESHOT) -> Optional[bytes]:
    """Launch region-selection capture tool, return raw PNG bytes or None if cancelled."""
    if tool == TOOL_SPECTACLE:
        return _capture_spectacle()
    return _capture_flameshot()


def _capture_flameshot() -> Optional[bytes]:
    try:
        result = subprocess.run(
            ["flameshot", "gui", "--raw"],
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("Error: flameshot not found. Install: sudo apt install flameshot", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("Screenshot timed out.", file=sys.stderr)
        return None

    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def _capture_spectacle() -> Optional[bytes]:
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    os.unlink(tmp_path)  # spectacle creates the file itself; it must not pre-exist

    try:
        subprocess.run(
            ["spectacle", "--region", "--background", "--nonotify", "--output", tmp_path],
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("Error: spectacle not found. Install: sudo apt install kde-spectacle", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("Screenshot timed out.", file=sys.stderr)
        _unlink_safe(tmp_path)
        return None

    if not os.path.exists(tmp_path):
        return None  # user cancelled

    try:
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        _unlink_safe(tmp_path)

    return data if data else None


def _unlink_safe(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def read_clipboard() -> Optional[str]:
    """Read X11 PRIMARY selection (highlighted text), fall back to CLIPBOARD."""
    text = _try_xclip("primary") or _try_xsel("primary")
    if text:
        return text
    text = _try_xclip("clipboard") or _try_xsel("clipboard")
    return text or None


def _try_xclip(selection: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["xclip", "-selection", selection, "-o"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _try_xsel(selection: str) -> Optional[str]:
    flag = "--primary" if selection == "primary" else "--clipboard"
    try:
        result = subprocess.run(
            ["xsel", flag, "--output"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
