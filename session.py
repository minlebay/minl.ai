"""Desktop session detection (X11 vs Wayland)."""

from __future__ import annotations

import os


def is_wayland() -> bool:
    return (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )


def qt_argv(argv: list[str]) -> list[str]:
    """argv for QApplication; on Wayland, run the GUI through XWayland.

    The overlay relies on X11 window management — always-on-top, centering,
    window opacity and KWin blur via xprop — none of which a Wayland compositor
    offers to regular clients. Passing ``-platform xcb`` (instead of setting
    QT_QPA_PLATFORM) keeps child processes such as Spectacle native.
    """
    if (
        is_wayland()
        and os.environ.get("DISPLAY")
        and not os.environ.get("QT_QPA_PLATFORM")
        and "-platform" not in argv
    ):
        return [*argv, "-platform", "xcb"]
    return list(argv)
