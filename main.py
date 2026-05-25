"""minl.ai — Linux desktop AI assistant entry point.

CLI usage:
    python main.py --tray         # run as tray icon + hotkey daemon (default mode)
    python main.py --screenshot   # one-shot: capture region → overlay
    python main.py --text         # one-shot: clipboard → overlay
    python main.py --screenshot --headless   # print response to stdout
    python main.py --text --headless
"""

from __future__ import annotations

import argparse
import sys

import logger as _logger
from config import load_config, PROVIDER_GEMINI
from capture import capture_screenshot, read_clipboard
from ai import MinlAI
from voice import transcribe_audio, sounddevice_available


def _transcribe_fn(ai: MinlAI):
    """Return transcription callback if sounddevice is available, else None."""
    if not sounddevice_available():
        return None
    return lambda audio_bytes: transcribe_audio(audio_bytes, ai._config)


def _require_api_key(ai: MinlAI) -> None:
    cfg = ai._config.api
    if cfg.provider == PROVIDER_GEMINI:
        if not cfg.gemini_api_key:
            print(
                "Error: Gemini API key not set.\n"
                "Set GEMINI_API_KEY env var or add gemini_api_key to ~/.config/minlai/config.toml",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if not cfg.anthropic_api_key:
            print(
                "Error: Anthropic API key not set.\n"
                "Set ANTHROPIC_API_KEY env var or add anthropic_api_key to ~/.config/minlai/config.toml",
                file=sys.stderr,
            )
            sys.exit(1)


def run_screenshot_mode(ai: MinlAI, headless: bool = False) -> None:
    """Capture a screen region and send to the AI."""
    tool = ai._config.hotkeys.screenshot_tool
    print(f"Select a screen region ({tool})…")
    image_bytes = capture_screenshot(tool)
    if image_bytes is None:
        print("No region selected or capture cancelled.")
        return

    if headless:
        print("Sending to AI…")
        response = ai.ask_screenshot(image_bytes)
        print("\n─── minl.ai ────────────────────────────")
        print(response)
        print("────────────────────────────────────────")
    else:
        from overlay import run_overlay
        run_overlay(
            config=ai._config.overlay,
            on_follow_up=ai.follow_up,
            on_transcribe=_transcribe_fn(ai),
            initial_fn=lambda: ai.ask_screenshot(image_bytes),
        )


def run_text_mode(ai: MinlAI, headless: bool = False) -> None:
    """Read clipboard/selection and send to Claude."""
    text = read_clipboard()
    if not text:
        print("Nothing in clipboard or X11 selection.")
        return

    preview = text[:120].replace("\n", " ")
    print(f"Selected text: {preview!r}{'…' if len(text) > 120 else ''}")

    system = (
        "You are minl.ai, a concise desktop assistant. "
        "The user has selected text and wants your help with it. "
        "Be brief and directly useful."
    )

    if headless:
        print("Sending to AI…")
        response = ai.ask_text(text, system=system)
        print("\n─── minl.ai ────────────────────────────")
        print(response)
        print("────────────────────────────────────────")
    else:
        from overlay import run_overlay
        run_overlay(
            config=ai._config.overlay,
            on_follow_up=ai.follow_up,
            on_transcribe=_transcribe_fn(ai),
            initial_fn=lambda: ai.ask_text(text, system=system),
        )


def run_tray_mode(ai: MinlAI) -> None:
    """Start tray icon + hotkey daemon (the primary mode)."""
    import os
    # Qt needs DISPLAY; give a helpful error on pure Wayland/headless
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(
            "Error: no display found (DISPLAY / WAYLAND_DISPLAY not set).",
            file=sys.stderr,
        )
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("minl.ai")
    app.setQuitOnLastWindowClosed(False)  # keep alive even when overlays close

    if not QApplication.instance().platformName() in ("xcb", "wayland", "offscreen"):
        pass  # accept whatever platform Qt chose

    from tray import MinlTray
    tray = MinlTray(config=ai._config, ai=ai)
    tray.start_hotkeys()

    cfg = ai._config.hotkeys
    print(f"minl.ai running in tray.")
    print(f"  Screenshot : {cfg.screenshot}")
    print(f"  Clipboard  : {cfg.clipboard}")
    print("Right-click the tray icon or use the hotkeys. Ctrl+C to quit.\n")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nminl.ai stopped.")


def main() -> None:
    _logger.setup()
    _logger.get("main").info("minl.ai starting")
    parser = argparse.ArgumentParser(
        prog="minlai",
        description="minl.ai — Linux desktop AI assistant",
    )
    parser.add_argument(
        "--tray", "-T",
        action="store_true",
        help="Run as system tray icon with hotkey daemon (default mode)",
    )
    parser.add_argument(
        "--screenshot", "-s",
        action="store_true",
        help="One-shot: capture screen region and ask Claude",
    )
    parser.add_argument(
        "--text", "-t",
        action="store_true",
        help="One-shot: read clipboard/selection and ask Claude",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Print response to stdout instead of showing overlay",
    )
    args = parser.parse_args()

    # Default to tray mode when no flag given
    if not any([args.tray, args.screenshot, args.text]):
        args.tray = True

    config = load_config()
    ai = MinlAI(config)

    if args.screenshot:
        _require_api_key(ai)
        run_screenshot_mode(ai, headless=args.headless)
    elif args.text:
        _require_api_key(ai)
        run_text_mode(ai, headless=args.headless)
    else:
        run_tray_mode(ai)  # tray always starts; key checked when action is triggered


if __name__ == "__main__":
    main()
