"""System tray icon, global hotkey bridge, and capture threading for minl.ai."""

from __future__ import annotations

import sys
from typing import Optional

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QMenu,
    QPushButton, QSizePolicy, QSystemTrayIcon, QTextEdit, QVBoxLayout,
)

import logger as _log
from ai import MinlAI
from capture import capture_screenshot, read_clipboard
from config import Config, PROVIDER_GEMINI
from voice import transcribe_audio, voice_input_available

_logger = _log.get("tray")


# ------------------------------------------------------------------ #
# Worker: runs flameshot/spectacle capture off the main thread
# ------------------------------------------------------------------ #

class CaptureWorker(QThread):
    captured = pyqtSignal(bytes)
    cancelled = pyqtSignal()

    def __init__(self, tool: str) -> None:
        super().__init__()
        self._tool = tool

    def run(self) -> None:
        data = capture_screenshot(self._tool)
        if data:
            self.captured.emit(data)
        else:
            self.cancelled.emit()


# ------------------------------------------------------------------ #
# Bridge: marshals pynput callbacks → Qt signals on the main thread
# ------------------------------------------------------------------ #

class HotkeyBridge(QObject):
    screenshot_triggered = pyqtSignal()
    clipboard_triggered = pyqtSignal()


# ------------------------------------------------------------------ #
# Device monitor: polls audio input devices every 3 s
# ------------------------------------------------------------------ #

class _DeviceMonitor(QObject):
    device_connected    = pyqtSignal(str, str)   # display_name, source_name
    device_disconnected = pyqtSignal(str, str)

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._known: dict[str, str] = {}   # source_name → display_name
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        import voice as _voice
        self._known = {src: disp for disp, src in _voice.list_audio_devices()}
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        import voice as _voice
        try:
            current = {src: disp for disp, src in _voice.list_audio_devices()}
        except Exception:
            return
        for src, disp in current.items():
            if src not in self._known:
                self.device_connected.emit(disp, src)
        for src, disp in self._known.items():
            if src not in current:
                self.device_disconnected.emit(disp, src)
        self._known = current


# ------------------------------------------------------------------ #
# Tray icon
# ------------------------------------------------------------------ #

class MinlTray(QObject):
    def __init__(self, config: Config, ai: MinlAI) -> None:
        super().__init__()
        self._config = config
        self._ai = ai
        self._bridge = HotkeyBridge()
        self._bridge.screenshot_triggered.connect(self._on_screenshot)
        self._bridge.clipboard_triggered.connect(self._on_clipboard)

        self._overlays: list = []
        self._capture_worker: Optional[CaptureWorker] = None

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_icon())
        self._tray.setToolTip("minl.ai desktop assistant")
        self._tray.setContextMenu(self._build_menu())
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        self._device_monitor = _DeviceMonitor(self)
        self._device_monitor.device_connected.connect(self._on_mic_connected)
        self._device_monitor.device_disconnected.connect(self._on_mic_disconnected)
        self._device_monitor.start()

        _logger.info("Tray initialized")

    # ------------------------------------------------------------------ #
    # Menu
    # ------------------------------------------------------------------ #

    def _build_menu(self) -> QMenu:
        menu = QMenu()
        import themes as _themes
        c = _themes.get(self._config.overlay.theme)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {c['window_bg']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {c['btn']}; }}
            QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 8px; }}
        """)

        hk = self._config.hotkeys
        # Show hotkey in label text (not setShortcut — that misparses pynput format)
        act_screen = menu.addAction(f"Screenshot  [{hk.screenshot}]")
        act_screen.triggered.connect(self._on_screenshot)

        act_clip = menu.addAction(f"Clipboard / Selection  [{hk.clipboard}]")
        act_clip.triggered.connect(self._on_clipboard)

        menu.addSeparator()

        act_settings = menu.addAction("Settings…")
        act_settings.triggered.connect(self._on_settings)

        act_logs = menu.addAction("View Logs…")
        act_logs.triggered.connect(self._on_view_logs)

        menu.addSeparator()

        act_quit = menu.addAction("Quit minl.ai")
        act_quit.triggered.connect(QApplication.instance().quit)

        return menu

    # ------------------------------------------------------------------ #
    # Tray click
    # ------------------------------------------------------------------ #

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._tray.contextMenu().popup(
                self._tray.geometry().center()
            )

    # ------------------------------------------------------------------ #
    # Hotkey / menu action handlers
    # ------------------------------------------------------------------ #

    def _has_api_key(self) -> bool:
        cfg = self._config.api
        if cfg.provider == PROVIDER_GEMINI:
            return bool(cfg.gemini_api_key)
        return bool(cfg.anthropic_api_key)

    def _warn_no_key(self) -> None:
        provider = "Gemini" if self._config.api.provider == PROVIDER_GEMINI else "Anthropic"
        _logger.warning("No API key set for provider: %s", provider)
        self._tray.showMessage(
            "minl.ai — API key missing",
            f"No {provider} API key set. Open Settings to add it.",
            QSystemTrayIcon.MessageIcon.Warning,
            4000,
        )
        self._on_settings()

    def _on_screenshot(self) -> None:
        _logger.info("Screenshot triggered (tool=%s)", self._config.hotkeys.screenshot_tool)
        if not self._has_api_key():
            self._warn_no_key()
            return
        if self._capture_worker and self._capture_worker.isRunning():
            return
        self._ai.reset_session()
        self._capture_worker = CaptureWorker(self._config.hotkeys.screenshot_tool)
        self._capture_worker.captured.connect(self._on_screenshot_captured)
        self._capture_worker.cancelled.connect(self._on_screenshot_cancelled)
        self._capture_worker.start()

    def _transcribe_callback(self):
        if not voice_input_available():
            return None
        cfg = self._config
        return lambda audio_bytes: transcribe_audio(audio_bytes, cfg)

    def _on_screenshot_captured(self, image_bytes: bytes) -> None:
        _logger.info("Screenshot captured (%d bytes)", len(image_bytes))
        from overlay import show_overlay
        overlay = show_overlay(
            config=self._config.overlay,
            on_follow_up=self._ai.follow_up,
            on_transcribe=self._transcribe_callback(),
            initial_fn=lambda: self._ai.ask_screenshot(image_bytes),
        )
        self._overlays.append(overlay)
        overlay.destroyed.connect(
            lambda: self._overlays.remove(overlay) if overlay in self._overlays else None
        )

    def _on_screenshot_cancelled(self) -> None:
        _logger.debug("Screenshot cancelled by user")

    def _on_clipboard(self) -> None:
        _logger.info("Clipboard triggered")
        if not self._has_api_key():
            self._warn_no_key()
            return
        text = read_clipboard()
        if not text:
            self._tray.showMessage(
                "minl.ai",
                "Nothing in clipboard or X11 selection.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            return
        _logger.info("Clipboard text: %d chars", len(text))
        self._ai.reset_session()
        system = (
            "You are minl.ai, a concise desktop assistant. "
            "The user has selected text and wants your help with it. "
            "Be brief and directly useful."
        )
        from overlay import show_overlay
        overlay = show_overlay(
            config=self._config.overlay,
            on_follow_up=self._ai.follow_up,
            on_transcribe=self._transcribe_callback(),
            initial_fn=lambda: self._ai.ask_text(text, system=system),
        )
        self._overlays.append(overlay)
        overlay.destroyed.connect(
            lambda: self._overlays.remove(overlay) if overlay in self._overlays else None
        )

    def _on_settings(self) -> None:
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._config)
        if dlg.exec():
            self._ai.reload()
            self._tray.setContextMenu(self._build_menu())
            self._restart_hotkeys()
            _logger.info("Settings saved, hotkeys restarted")

    def _on_mic_connected(self, display: str, source: str) -> None:
        preferred = self._config.overlay.audio_device
        if preferred and source == preferred:
            _logger.info("Preferred mic reconnected: %s", source)
            self._tray.showMessage(
                "minl.ai", f"Microphone reconnected: {display}",
                QSystemTrayIcon.MessageIcon.Information, 3000,
            )

    def _on_mic_disconnected(self, display: str, source: str) -> None:
        preferred = self._config.overlay.audio_device
        if preferred and source == preferred:
            _logger.info("Preferred mic disconnected: %s, fallback to default", source)
            self._tray.showMessage(
                "minl.ai",
                f"Microphone disconnected: {display}\nFalling back to system default.",
                QSystemTrayIcon.MessageIcon.Warning, 4000,
            )

    def _on_view_logs(self) -> None:
        dlg = _LogViewerDialog(_log.LOG_FILE, self._config.overlay.theme)
        dlg.exec()

    # ------------------------------------------------------------------ #
    # Hotkey listener (pynput)
    # ------------------------------------------------------------------ #

    def start_hotkeys(self) -> None:
        self._hotkey_thread = _HotkeyThread(self._config, self._bridge)
        self._hotkey_thread.daemon = True
        self._hotkey_thread.start()

    def _restart_hotkeys(self) -> None:
        if hasattr(self, "_hotkey_thread"):
            self._hotkey_thread.stop()
        self.start_hotkeys()


# ------------------------------------------------------------------ #
# Log viewer dialog
# ------------------------------------------------------------------ #

class _LogViewerDialog(QDialog):
    _MAX_LINES = 500

    def __init__(self, log_path, theme: str) -> None:
        super().__init__()
        self._log_path = log_path
        self.setWindowTitle("minl.ai — Logs")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text)

        btns = QDialogButtonBox()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load)
        btns.addButton(refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)
        btns.addButton(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        import themes as _themes
        self.setStyleSheet(_themes.dialog_style(theme))

        self._load()

    def _load(self) -> None:
        try:
            text = self._log_path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            if len(lines) > self._MAX_LINES:
                lines = lines[-self._MAX_LINES:]
            self._text.setPlainText("\n".join(lines))
            # Scroll to bottom
            sb = self._text.verticalScrollBar()
            sb.setValue(sb.maximum())
        except FileNotFoundError:
            self._text.setPlainText("No log file yet.")
        except Exception as exc:
            self._text.setPlainText(f"Error reading log: {exc}")


# ------------------------------------------------------------------ #
# Hotkey listener thread (pynput runs its own loop)
# ------------------------------------------------------------------ #

class _HotkeyThread:
    def __init__(self, config: Config, bridge: HotkeyBridge) -> None:
        self._config = config
        self._bridge = bridge
        self._listener = None
        self._log = _log.get("hotkeys")

    def start(self) -> None:
        import threading
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            from pynput import keyboard
        except ImportError:
            self._log.error("pynput not installed — hotkeys disabled")
            return

        hk_screenshot = self._config.hotkeys.screenshot
        hk_clipboard = self._config.hotkeys.clipboard
        self._log.info("Registering hotkeys: screenshot=%r  clipboard=%r",
                       hk_screenshot, hk_clipboard)

        def _on_screenshot():
            self._log.debug("Screenshot hotkey fired")
            self._bridge.screenshot_triggered.emit()

        def _on_clipboard():
            self._log.debug("Clipboard hotkey fired")
            self._bridge.clipboard_triggered.emit()

        try:
            self._listener = keyboard.GlobalHotKeys({
                hk_screenshot: _on_screenshot,
                hk_clipboard:  _on_clipboard,
            })
            self._log.info("Hotkey listener started OK")
            self._listener.run()
            self._log.info("Hotkey listener stopped")
        except Exception as exc:
            self._log.error("Hotkey listener failed: %s", exc, exc_info=True)


# ------------------------------------------------------------------ #
# Icon generator
# ------------------------------------------------------------------ #

def _make_icon() -> QIcon:
    from pathlib import Path

    svg_candidates = [
        Path(__file__).parent / "minlai.svg",
        Path("/usr/share/icons/hicolor/scalable/apps/minlai.svg"),
    ]
    for path in svg_candidates:
        if path.exists():
            return QIcon(str(path))

    size = 64
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor("#1a1a2e")))
    p.setPen(QPen(QColor("#6d90a8"), 2))
    p.drawEllipse(2, 2, size - 4, size - 4)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#6d90a8"), 2))
    p.drawEllipse(8, 22, size - 16, 20)
    p.setBrush(QBrush(QColor("#6d90a8")))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(26, 26, 12, 12)
    p.setBrush(QBrush(QColor("#a0b8cc")))
    p.drawEllipse(size - 12, 29, 7, 7)
    p.end()
    return QIcon(pix)
