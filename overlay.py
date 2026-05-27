"""PyQt6 floating overlay window for displaying AI responses."""

from __future__ import annotations

import re
import sys
import threading
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QRectF, QSize, QThread, pyqtSignal, QObject
from PyQt6.QtGui import (
    QColor, QIcon, QKeySequence, QPainter, QPen,
    QPixmap, QShortcut, QTextCursor, QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import themes
from config import OverlayConfig

APP_NAME = "minl.ai"

_RGBA_RE = re.compile(r'rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)')
_HEX_RE  = re.compile(r'#([0-9a-fA-F]{6})')


def _syntax_highlight(html: str, theme: str) -> str:
    """Replace fenced code blocks with Pygments inline-styled HTML."""
    import re
    import html as _html_lib
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, TextLexer
        from pygments.formatters import HtmlFormatter
    except ImportError:
        return html

    style = "monokai" if theme == "dark" else "friendly"
    fmt = HtmlFormatter(inline_styles=True, nowrap=True)
    bg = "#1a1c1f" if theme == "dark" else "#f0f2f7"
    border = "rgba(72,78,88,0.6)" if theme == "dark" else "rgba(148,162,185,0.8)"

    def _hilite(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        code = _html_lib.unescape(m.group(2))
        try:
            lexer = get_lexer_by_name(lang, stripall=True) if lang else TextLexer()
        except Exception:
            lexer = TextLexer()
        highlighted = highlight(code, lexer, fmt).rstrip()
        return (
            f'<pre style="background:{bg};padding:8px 12px;'
            f'border:1px solid {border};border-radius:4px;'
            f'font-family:monospace;margin:4px 0">'
            f'<code>{highlighted}</code></pre>'
        )

    return re.sub(
        r'<pre><code(?:\s+class="language-([^"]*)")?>(.*?)</code></pre>',
        _hilite,
        html,
        flags=re.DOTALL,
    )


def _md_to_html(text: str, theme: str = "dark") -> str:
    """Convert Markdown to HTML with optional syntax highlighting."""
    try:
        import markdown as _md
        html = _md.markdown(text, extensions=["fenced_code", "tables"])
        return _syntax_highlight(html, theme)
    except ImportError:
        doc = QTextDocument()
        doc.setMarkdown(text)
        return doc.toHtml()


def _parse_rgba(s: str) -> QColor:
    m = _RGBA_RE.match(s)
    if m:
        return QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                      round(float(m.group(4)) * 255))
    m = _HEX_RE.match(s)
    if m:
        return QColor(f"#{m.group(1)}")
    return QColor(24, 25, 27, 220)


def _kwin_blur(win_id: int, width: int, height: int, enabled: bool) -> None:
    """Set/remove _KDE_NET_WM_BLUR_BEHIND_REGION so KWin blurs the area behind the window."""
    import os, subprocess
    if not os.environ.get("DISPLAY"):
        return
    try:
        wid = hex(int(win_id))
        if enabled:
            subprocess.run(
                ["xprop", "-id", wid,
                 "-f", "_KDE_NET_WM_BLUR_BEHIND_REGION", "32c",
                 "-set", "_KDE_NET_WM_BLUR_BEHIND_REGION",
                 f"0, 0, {width}, {height}"],
                capture_output=True, timeout=3, check=False,
            )
        else:
            subprocess.run(
                ["xprop", "-id", wid, "-remove", "_KDE_NET_WM_BLUR_BEHIND_REGION"],
                capture_output=True, timeout=3, check=False,
            )
    except Exception:
        pass


def _paint_mic_icon(size: int, color: QColor) -> QPixmap:
    """Draw a schematic microphone: capsule + arc base + stem + foot."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, max(1.3, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = float(size)
    cx = s / 2
    cw, ch = s * 0.40, s * 0.45
    # Capsule body
    p.drawRoundedRect(QRectF(cx - cw / 2, s * 0.05, cw, ch), cw / 2, cw / 2)
    # Base arc (∪-shape)
    arm = s * 0.25
    cap_bot = s * 0.05 + ch
    p.drawArc(QRectF(cx - arm, cap_bot - arm, arm * 2, arm * 2), 180 * 16, -180 * 16)
    # Stem
    arc_bot = cap_bot + arm
    p.drawLine(int(cx), int(arc_bot), int(cx), int(s * 0.88))
    # Foot
    fw = s * 0.20
    p.drawLine(int(cx - fw), int(s * 0.88), int(cx + fw), int(s * 0.88))
    p.end()
    return pix


def _paint_stop_icon(size: int, color: QColor) -> QPixmap:
    """Draw a filled rounded square (stop/record indicator)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    m = size * 0.25
    p.drawRoundedRect(QRectF(m, m, size - 2 * m, size - 2 * m), 2.5, 2.5)
    p.end()
    return pix


class _CentralWidget(QWidget):
    """Central widget with paintEvent override so Qt stylesheet background: renders."""

    def paintEvent(self, event) -> None:
        from PyQt6.QtWidgets import QStyleOption, QStyle
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()


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


class MinlOverlay(QMainWindow):
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
        self._recorder = None
        self._last_fn: Optional[Callable[[], str]] = None
        self._message_history: list[tuple[str, str]] = []
        self._is_loading: bool = False

        self._build_ui()
        self._apply_style()

        if loading:
            self._set_loading()
        elif initial_response:
            self._append_message(APP_NAME, initial_response)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self._config.width, self._config.height)
        self._center_on_screen()

        central = _CentralWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

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
            self._mic_btn = QPushButton()
            self._mic_btn.setObjectName("micBtn")
            self._mic_btn.setToolTip("Click to record voice")
            self._mic_btn.clicked.connect(self._on_mic_clicked)
            self._refresh_mic_icon()
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

    def _refresh_mic_icon(self, state: str = "idle") -> None:
        if self._mic_btn is None:
            return
        sz = self._config.font_size + 6
        c = themes.get(self._config.theme)
        if state == "recording":
            icon_pix = _paint_stop_icon(sz, _parse_rgba(c['mic_rec_text']))
        else:
            color_key = 'text_muted' if state == "transcribing" else 'mic_text'
            icon_pix = _paint_mic_icon(sz, _parse_rgba(c[color_key]))
        self._mic_btn.setIcon(QIcon(icon_pix))
        self._mic_btn.setIconSize(QSize(sz, sz))

    def _apply_style(self) -> None:
        self.setStyleSheet(themes.overlay_style(self._config.font_size, self._config.theme))
        self.setWindowOpacity(self._config.opacity)
        self._refresh_mic_icon()

    def _apply_blur(self) -> None:
        """Ask KWin to blur the desktop region behind this window."""
        if not self._config.blur_enabled:
            return
        _kwin_blur(int(self.winId()), self.width(), self.height(), enabled=True)
        self.setStyleSheet(
            themes.overlay_style(self._config.font_size, self._config.theme, blur_bg=True)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._config.blur_enabled:
            _kwin_blur(int(self.winId()), self.width(), self.height(), enabled=True)

    # ------------------------------------------------------------------ #
    # Chat helpers
    # ------------------------------------------------------------------ #

    def _c(self) -> dict[str, str]:
        return themes.get(self._config.theme)

    def _rebuild_chat_html(self) -> None:
        c = self._c()
        parts: list[str] = []
        for role, text in self._message_history:
            if role == "_error":
                parts.append(
                    f'<div style="margin:0 0 8px 0">'
                    f'<span style="color:{c["error"]}">Error: {_escape_html(text)}</span>'
                    f'</div>'
                )
            else:
                color = c["ai_color"] if role == APP_NAME else c["user_color"]
                header = (
                    f'<b><span style="color:{color}">{role}</span></b>'
                    f'<span style="color:{c["separator"]}"> ▸ </span>'
                )
                if role == APP_NAME:
                    body = _md_to_html(text, self._config.theme)
                else:
                    body = f'<span style="color:{c["text"]}">{_escape_html(text)}</span>'
                parts.append(f'<div style="margin:0 0 8px 0">{header}{body}</div>')
        if self._is_loading:
            parts.append(
                f'<div><span style="color:{c["thinking"]};font-style:italic">Thinking…</span></div>'
            )
        self._chat.setHtml(''.join(parts) if parts else '')

    def _append_message(self, role: str, text: str) -> None:
        self._message_history.append((role, text))
        self._rebuild_chat_html()
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

    def _set_loading(self) -> None:
        self._is_loading = True
        self._rebuild_chat_html()
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

    def _set_error(self, msg: str) -> None:
        self._message_history.append(("_error", msg))
        self._rebuild_chat_html()
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

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
        self._is_loading = True
        self._rebuild_chat_html()
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

    def _on_worker_result(self, text: str) -> None:
        self._is_loading = False
        self._retry_btn.setVisible(False)
        self._message_history.append((APP_NAME, text))
        self._rebuild_chat_html()
        self._chat.moveCursor(QTextCursor.MoveOperation.End)

    def _on_worker_error(self, msg: str) -> None:
        import logger as _log
        _log.get("overlay").error("AI error: %s", msg)
        self._is_loading = False
        self._message_history.append(("_error", msg))
        self._rebuild_chat_html()
        self._retry_btn.setVisible(True)

    def _on_worker_done(self) -> None:
        self._worker = None

    def _on_retry(self) -> None:
        if self._last_fn is None or self._worker is not None:
            return
        self._retry_btn.setVisible(False)
        self._message_history.clear()
        self._is_loading = False
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
        device = self._config.audio_device
        if _voice.is_muted(device):
            self._set_error("Microphone is muted. Unmute it in system audio settings.")
            return
        try:
            self._recorder = _voice.VoiceRecorder(device=device)
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
            self._mic_btn.setProperty("recording", "true")
            self._mic_btn.setToolTip("Recording… click to stop")
            self._input.setPlaceholderText("Listening…")
            self._mic_btn.setEnabled(True)
        elif state == "transcribing":
            self._mic_btn.setProperty("recording", "false")
            self._mic_btn.setToolTip("Transcribing…")
            self._input.setPlaceholderText("Transcribing…")
            self._mic_btn.setEnabled(False)
        else:  # idle
            self._mic_btn.setProperty("recording", "false")
            self._mic_btn.setToolTip("Click to record voice")
            self._input.setPlaceholderText("Ask a follow-up question…")
            self._mic_btn.setEnabled(True)
        self._refresh_mic_icon(state)
        # Force Qt to re-evaluate the stylesheet for property changes
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)

    # ------------------------------------------------------------------ #
    # Public: push initial AI response once it arrives
    # ------------------------------------------------------------------ #

    def show_response(self, text: str) -> None:
        self._retry_btn.setVisible(False)
        self._is_loading = False
        self._message_history = [(APP_NAME, text)]
        self._rebuild_chat_html()
        self._chat.moveCursor(QTextCursor.MoveOperation.Start)

    def show_error(self, msg: str) -> None:
        self._is_loading = False
        self._message_history = [("_error", msg)]
        self._rebuild_chat_html()
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
) -> "MinlOverlay":
    """Create and show overlay within an already-running QApplication event loop."""
    overlay = MinlOverlay(
        config=config,
        on_follow_up=on_follow_up,
        on_transcribe=on_transcribe,
        loading=initial_fn is not None,
    )
    overlay.show()
    overlay._apply_blur()  # set KWin blur AFTER window is mapped
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
