"""PyQt6 floating overlay window for displaying AI responses."""

from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QThread, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import themes
from config import OverlayConfig

APP_NAME = "minl.ai"


class _DragBar(QWidget):
    """Title bar that acts as a drag handle for the frameless window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._drag_start: QPoint | None = None
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_start)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)


class WorkerSignals(QObject):
    result = pyqtSignal(str)
    error = pyqtSignal(str)
    started = pyqtSignal()


class AIWorker(QThread):
    """Run AI calls off the main thread."""

    def __init__(self, fn: Callable[[], str]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()

    def run(self) -> None:
        self.signals.started.emit()
        try:
            result = self.fn()
            self.signals.result.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class _VoiceWorker(QThread):
    """Stop recording → convert to WAV → transcribe. All in one background step."""

    transcribed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        recorder: "voice.VoiceRecorder",
        transcribe_fn: Callable[[bytes], str],
    ) -> None:
        super().__init__()
        self._recorder = recorder
        self._transcribe_fn = transcribe_fn

    def run(self) -> None:
        try:
            audio_bytes = self._recorder.stop()
            if not audio_bytes:
                self.transcribed.emit("")
                return
            text = self._transcribe_fn(audio_bytes)
            self.transcribed.emit(text)
        except Exception as exc:
            self.error.emit(str(exc))


class OrbitOverlay(QMainWindow):
    def __init__(
        self,
        config: OverlayConfig,
        on_follow_up: Callable[[str], str],
        on_transcribe: Optional[Callable[[bytes], str]] = None,
        initial_response: str = "",
        loading: bool = False,
    ) -> None:
        super().__init__()
        self._config = config
        self._on_follow_up = on_follow_up
        self._on_transcribe = on_transcribe
        self._worker: Optional[AIWorker] = None
        self._voice_worker: Optional[_VoiceWorker] = None
        self._recorder = None  # created lazily when mic button pressed
        self._last_fn: Optional[Callable[[], str]] = None

        self._build_ui()
        self._apply_style()

        if loading:
            self._set_loading()
        elif initial_response:
            self._append_message("Orbit", initial_response)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self._config.width, self._config.height)
        self._center_on_screen()

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title bar
        title_bar = self._build_title_bar()
        layout.addWidget(title_bar)

        # Chat area
        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setObjectName("chat")
        layout.addWidget(self._chat, stretch=1)

        # Input row
        input_row = self._build_input_row()
        layout.addWidget(input_row)

        # Escape shortcut
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self.close)

    def _build_title_bar(self) -> QWidget:
        bar = _DragBar(self)
        bar.setObjectName("titleBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("◎")
        icon.setObjectName("titleIcon")
        h.addWidget(icon)

        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        h.addWidget(title)
        h.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close)
        close_btn.setToolTip("Close (Esc)")
        h.addWidget(close_btn)

        return bar

    def _build_input_row(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self._input = QLineEdit()
        self._input.setObjectName("inputField")
        self._input.setPlaceholderText("Ask a follow-up question…")
        self._input.returnPressed.connect(self._on_send)
        h.addWidget(self._input, stretch=1)

        # Mic button — only shown when a transcribe callback is provided
        self._mic_btn: Optional[QPushButton] = None
        if self._on_transcribe is not None:
            self._mic_btn = QPushButton("🎙")
            self._mic_btn.setObjectName("micBtn")
            self._mic_btn.setFixedWidth(36)
            self._mic_btn.setToolTip("Hold to record voice (click to start/stop)")
            self._mic_btn.clicked.connect(self._on_mic_clicked)
            h.addWidget(self._mic_btn)

        self._retry_btn = QPushButton("↺ Retry")
        self._retry_btn.setObjectName("retryBtn")
        self._retry_btn.clicked.connect(self._on_retry)
        self._retry_btn.setVisible(False)
        h.addWidget(self._retry_btn)

        send_btn = QPushButton("Send")
        send_btn.setObjectName("sendBtn")
        send_btn.clicked.connect(self._on_send)
        h.addWidget(send_btn)

        return row

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self._config.width) // 2
            y = (geo.height() - self._config.height) // 2
            self.move(geo.x() + x, geo.y() + y)

    # ------------------------------------------------------------------ #
    # Style
    # ------------------------------------------------------------------ #

    def _apply_style(self) -> None:
        self.setStyleSheet(themes.overlay_style(self._config.font_size, self._config.theme))
        self.setWindowOpacity(self._config.opacity)

    # ------------------------------------------------------------------ #
    # Chat helpers
    # ------------------------------------------------------------------ #

    def _c(self) -> dict[str, str]:
        return themes.get(self._config.theme)

    def _append_message(self, role: str, text: str) -> None:
        c = self._c()
        color = c["ai_color"] if role == APP_NAME else c["user_color"]
        self._chat.append(
            f'<span style="color:{color};font-weight:bold">{role}</span>'
            f'<span style="color:{c["separator"]}"> ▸ </span>'
            f'<span style="color:{c["text"]}">{_escape_html(text)}</span>'
            "<br>"
        )
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

    def _set_loading(self) -> None:
        c = self._c()
        self._chat.setHtml(
            f'<span style="color:{c["thinking"]};font-style:italic">Thinking…</span>'
        )

    def _set_error(self, msg: str) -> None:
        c = self._c()
        self._chat.append(
            f'<span style="color:{c["error"]}">Error: {_escape_html(msg)}</span><br>'
        )

    # ------------------------------------------------------------------ #
    # Send / receive
    # ------------------------------------------------------------------ #

    def _on_send(self) -> None:
        question = self._input.text().strip()
        if not question or self._worker is not None:
            return

        self._retry_btn.setVisible(False)
        self._input.clear()
        self._append_message("You", question)
        self._start_worker(lambda: self._on_follow_up(question))

    def _start_worker(self, fn: Callable[[], str]) -> None:
        self._last_fn = fn
        self._worker = AIWorker(fn)
        self._worker.signals.started.connect(self._on_worker_started)
        self._worker.signals.result.connect(self._on_worker_result)
        self._worker.signals.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _on_worker_started(self) -> None:
        c = self._c()
        self._chat.append(
            f'<span style="color:{c["thinking"]};font-style:italic">Thinking…</span><br>'
        )
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

    def _on_worker_result(self, text: str) -> None:
        self._remove_last_para()
        self._retry_btn.setVisible(False)
        self._append_message(APP_NAME, text)

    def _on_worker_error(self, msg: str) -> None:
        import logger as _log
        _log.get("overlay").error("AI error: %s", msg)
        self._remove_last_para()
        self._set_error(msg)
        self._retry_btn.setVisible(True)

    def _on_worker_done(self) -> None:
        self._worker = None

    def _on_retry(self) -> None:
        if self._last_fn is None or self._worker is not None:
            return
        self._retry_btn.setVisible(False)
        self._chat.clear()
        self._start_worker(self._last_fn)

    # ------------------------------------------------------------------ #
    # Mic / voice input
    # ------------------------------------------------------------------ #

    def _on_mic_clicked(self) -> None:
        if self._voice_worker is not None and self._voice_worker.isRunning():
            return  # transcription already in progress

        if self._recorder is None or not self._recorder.is_recording:
            self._start_recording()
        else:
            self._stop_and_transcribe()

    def _start_recording(self) -> None:
        import voice as _voice
        if not _voice.sounddevice_available():
            self._set_error("sounddevice not installed. Run: pip install sounddevice")
            return
        try:
            self._recorder = _voice.VoiceRecorder()
            self._recorder.start()
        except Exception as exc:
            import logger as _log
            _log.get("overlay").error("Microphone error: %s", exc, exc_info=True)
            self._set_error(f"Microphone error: {exc}")
            self._recorder = None
            return
        self._set_mic_state("recording")

    def _stop_and_transcribe(self) -> None:
        self._set_mic_state("transcribing")
        import voice as _voice
        self._voice_worker = _VoiceWorker(self._recorder, self._on_transcribe)
        self._voice_worker.transcribed.connect(self._on_transcription_done)
        self._voice_worker.error.connect(self._on_transcription_error)
        self._voice_worker.finished.connect(lambda: setattr(self, "_voice_worker", None))
        self._voice_worker.start()

    def _on_transcription_done(self, text: str) -> None:
        self._set_mic_state("idle")
        if text:
            self._input.setText(text)
            self._input.setFocus()

    def _on_transcription_error(self, msg: str) -> None:
        self._set_mic_state("idle")
        self._set_error(msg)

    def _set_mic_state(self, state: str) -> None:
        if self._mic_btn is None:
            return
        if state == "recording":
            self._mic_btn.setText("⏹")
            self._mic_btn.setProperty("recording", "true")
            self._mic_btn.setToolTip("Recording… click to stop")
            self._input.setPlaceholderText("Listening…")
            self._mic_btn.setEnabled(True)
        elif state == "transcribing":
            self._mic_btn.setText("…")
            self._mic_btn.setProperty("recording", "false")
            self._mic_btn.setToolTip("Transcribing…")
            self._input.setPlaceholderText("Transcribing…")
            self._mic_btn.setEnabled(False)
        else:  # idle
            self._mic_btn.setText("🎙")
            self._mic_btn.setProperty("recording", "false")
            self._mic_btn.setToolTip("Click to record voice")
            self._input.setPlaceholderText("Ask a follow-up question…")
            self._mic_btn.setEnabled(True)
        # Force Qt to re-evaluate the stylesheet for property changes
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)

    def _remove_last_para(self) -> None:
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()

    # ------------------------------------------------------------------ #
    # Public: push initial AI response once it arrives
    # ------------------------------------------------------------------ #

    def show_response(self, text: str) -> None:
        self._retry_btn.setVisible(False)
        self._chat.clear()
        self._append_message(APP_NAME, text)

    def show_error(self, msg: str) -> None:
        self._chat.clear()
        self._set_error(msg)
        self._retry_btn.setVisible(True)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


def show_overlay(
    config: OverlayConfig,
    on_follow_up: Callable[[str], str],
    on_transcribe: Optional[Callable[[bytes], str]] = None,
    initial_fn: Optional[Callable[[], str]] = None,
) -> "OrbitOverlay":
    """Create and show overlay within an already-running QApplication event loop."""
    overlay = OrbitOverlay(
        config=config,
        on_follow_up=on_follow_up,
        on_transcribe=on_transcribe,
        loading=initial_fn is not None,
    )
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()

    if initial_fn is not None:
        overlay._last_fn = initial_fn
        worker = AIWorker(initial_fn)
        worker.signals.result.connect(overlay.show_response)
        worker.signals.error.connect(overlay.show_error)
        worker.start()
        overlay._initial_worker = worker  # type: ignore[attr-defined]

    return overlay


def run_overlay(
    config: OverlayConfig,
    on_follow_up: Callable[[str], str],
    on_transcribe: Optional[Callable[[bytes], str]] = None,
    initial_fn: Optional[Callable[[], str]] = None,
) -> None:
    """Create QApplication (if needed), show overlay, run event loop."""
    app = QApplication.instance() or QApplication(sys.argv)
    show_overlay(config, on_follow_up, on_transcribe, initial_fn)
    app.exec()
