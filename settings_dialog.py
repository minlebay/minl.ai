"""Settings dialog — edits ~/.config/minlai/config.toml via a PyQt6 form."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import themes
from config import (
    Config,
    PROVIDER_ANTHROPIC,
    PROVIDER_GEMINI,
    DEFAULT_MODEL,
    is_autostart_enabled,
    save_config,
    set_autostart,
)

ANTHROPIC_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5-20251001",
]

GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

STT_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

PROVIDERS = [
    ("Anthropic (Claude)", PROVIDER_ANTHROPIC),
    ("Google Gemini",      PROVIDER_GEMINI),
]

THEMES = [
    ("Dark (gray)", "dark"),
    ("Light",       "light"),
]

SCREENSHOT_TOOLS = [
    ("Flameshot",       "flameshot"),
    ("Spectacle (KDE)", "spectacle"),
]

LANGUAGES = [
    ("Auto (match input language)", "auto"),
    ("English",                     "English"),
    ("Russian / Русский",           "Russian"),
    ("German / Deutsch",            "German"),
    ("French / Français",           "French"),
    ("Spanish / Español",           "Spanish"),
    ("Italian / Italiano",          "Italian"),
    ("Portuguese / Português",      "Portuguese"),
    ("Chinese / 中文",               "Chinese"),
    ("Japanese / 日本語",             "Japanese"),
    ("Korean / 한국어",               "Korean"),
    ("Arabic / العربية",             "Arabic"),
]


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("minl.ai — Settings")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setMinimumWidth(480)
        self._build_ui()
        self._apply_style()
        self._load_values()
        self._on_provider_changed()  # sync model list to loaded provider

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(self._build_provider_group())
        layout.addWidget(self._build_keys_group())
        layout.addWidget(self._build_model_group())
        layout.addWidget(self._build_hotkeys_group())
        layout.addWidget(self._build_overlay_group())
        layout.addWidget(self._build_voice_group())

        self._autostart_cb = QCheckBox("Launch at login  (adds ~/.config/autostart/minlai.desktop)")
        layout.addWidget(self._autostart_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save")
        layout.addWidget(buttons)

    def _build_provider_group(self) -> QGroupBox:
        box = QGroupBox("Provider")
        h = QHBoxLayout(box)
        h.setSpacing(10)

        self._provider = QComboBox()
        for label, _ in PROVIDERS:
            self._provider.addItem(label)
        self._provider.currentIndexChanged.connect(self._on_provider_changed)
        h.addWidget(self._provider)
        h.addStretch()
        return box

    def _build_keys_group(self) -> QGroupBox:
        box = QGroupBox("API Keys")
        form = QFormLayout(box)
        form.setSpacing(8)

        self._anthropic_key = self._key_row()
        form.addRow("Anthropic:", self._anthropic_key)

        self._gemini_key = self._key_row()
        form.addRow("Gemini:", self._gemini_key)

        return box

    def _key_row(self) -> QWidget:
        """A password field with Show/Hide toggle."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        h.addWidget(field)

        toggle = QPushButton("Show")
        toggle.setFixedWidth(48)
        toggle.setCheckable(True)
        toggle.toggled.connect(
            lambda on, f=field, b=toggle: (
                f.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password),
                b.setText("Hide" if on else "Show"),
            )
        )
        h.addWidget(toggle)

        row._field = field  # type: ignore[attr-defined]
        return row

    def _build_model_group(self) -> QGroupBox:
        box = QGroupBox("Model")
        form = QFormLayout(box)
        form.setSpacing(8)

        self._model = QComboBox()
        self._model.setEditable(True)
        form.addRow("Model:", self._model)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(256, 32768)
        self._max_tokens.setSingleStep(256)
        form.addRow("Max tokens:", self._max_tokens)

        self._language = QComboBox()
        for label, _ in LANGUAGES:
            self._language.addItem(label)
        form.addRow("Response language:", self._language)

        self._stt_model = QComboBox()
        self._stt_model.setEditable(True)
        for m in STT_MODELS:
            self._stt_model.addItem(m)
        self._stt_model.setToolTip(
            "Gemini model used for voice transcription.\n"
            "Always requires a Gemini API key regardless of the main provider."
        )
        form.addRow("Voice STT model:", self._stt_model)

        return box

    def _build_hotkeys_group(self) -> QGroupBox:
        box = QGroupBox("Hotkeys  (pynput format, e.g. <ctrl>+<shift>+a)")
        form = QFormLayout(box)
        form.setSpacing(8)

        self._screenshot_tool = QComboBox()
        for label, _ in SCREENSHOT_TOOLS:
            self._screenshot_tool.addItem(label)
        form.addRow("Screenshot tool:", self._screenshot_tool)

        self._hk_screenshot = QLineEdit()
        form.addRow("Screenshot hotkey:", self._hk_screenshot)
        self._hk_clipboard = QLineEdit()
        form.addRow("Clipboard hotkey:", self._hk_clipboard)
        return box

    def _build_overlay_group(self) -> QGroupBox:
        box = QGroupBox("Overlay window")
        form = QFormLayout(box)
        form.setSpacing(8)

        size_row = QWidget()
        h = QHBoxLayout(size_row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self._width = QSpinBox()
        self._width.setRange(320, 1920)
        self._width.setSuffix(" px")
        self._height = QSpinBox()
        self._height.setRange(200, 1080)
        self._height.setSuffix(" px")
        h.addWidget(QLabel("W:"))
        h.addWidget(self._width)
        h.addWidget(QLabel("H:"))
        h.addWidget(self._height)
        h.addStretch()
        form.addRow("Size:", size_row)

        self._opacity = QDoubleSpinBox()
        self._opacity.setRange(0.3, 1.0)
        self._opacity.setSingleStep(0.05)
        self._opacity.setDecimals(2)
        form.addRow("Opacity:", self._opacity)

        self._font_size = QSpinBox()
        self._font_size.setRange(8, 24)
        self._font_size.setSuffix(" pt")
        form.addRow("Font size:", self._font_size)

        self._theme = QComboBox()
        for label, _ in THEMES:
            self._theme.addItem(label)
        form.addRow("Theme:", self._theme)

        blur_row = QWidget()
        h_blur = QHBoxLayout(blur_row)
        h_blur.setContentsMargins(0, 0, 0, 0)
        h_blur.setSpacing(8)
        self._blur_cb = QCheckBox("Enable")
        h_blur.addWidget(self._blur_cb)
        h_blur.addWidget(QLabel("Radius:"))
        self._blur_radius = QSpinBox()
        self._blur_radius.setRange(1, 30)
        self._blur_radius.setSuffix(" px")
        self._blur_radius.setEnabled(False)
        h_blur.addWidget(self._blur_radius)
        h_blur.addStretch()
        self._blur_cb.toggled.connect(self._blur_radius.setEnabled)
        form.addRow("Blur:", blur_row)

        self._corner_radius = QSpinBox()
        self._corner_radius.setRange(0, 20)
        self._corner_radius.setSuffix(" px")
        form.addRow("Corner radius:", self._corner_radius)

        return box

    def _build_voice_group(self) -> QGroupBox:
        box = QGroupBox("Voice Input")
        form = QFormLayout(box)
        form.setSpacing(8)

        device_row = QWidget()
        h = QHBoxLayout(device_row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self._audio_device = QComboBox()
        self._audio_device.setSizePolicy(
            self._audio_device.sizePolicy().horizontalPolicy(),
            self._audio_device.sizePolicy().verticalPolicy(),
        )
        self._audio_device.setMinimumWidth(260)
        h.addWidget(self._audio_device, stretch=1)

        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedWidth(32)
        refresh_btn.setToolTip("Refresh device list")
        refresh_btn.clicked.connect(self._refresh_audio_devices)
        h.addWidget(refresh_btn)

        form.addRow("Recording device:", device_row)
        self._refresh_audio_devices()
        return box

    def _refresh_audio_devices(self) -> None:
        import voice as _voice
        current = self._audio_device.currentData() or ""
        self._audio_device.blockSignals(True)
        self._audio_device.clear()
        self._audio_device.addItem("System default", "")
        for disp, src in _voice.list_audio_devices():
            self._audio_device.addItem(disp, src)
        # Restore selection
        idx = self._audio_device.findData(current)
        self._audio_device.setCurrentIndex(idx if idx >= 0 else 0)
        self._audio_device.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Style
    # ------------------------------------------------------------------ #

    def _apply_style(self) -> None:
        self.setStyleSheet(themes.dialog_style(self._config.overlay.theme))

    # ------------------------------------------------------------------ #
    # Provider switch
    # ------------------------------------------------------------------ #

    def _current_provider(self) -> str:
        idx = self._provider.currentIndex()
        return PROVIDERS[idx][1] if 0 <= idx < len(PROVIDERS) else PROVIDER_ANTHROPIC

    def _on_provider_changed(self) -> None:
        provider = self._current_provider()
        is_anthropic = provider == PROVIDER_ANTHROPIC

        # Highlight active key row, dim the other
        self._anthropic_key._field.setEnabled(is_anthropic)  # type: ignore[attr-defined]
        self._gemini_key._field.setEnabled(not is_anthropic)  # type: ignore[attr-defined]

        # Swap model list; keep custom value if user typed one
        current_model = self._model.currentText()
        models = ANTHROPIC_MODELS if is_anthropic else GEMINI_MODELS

        self._model.blockSignals(True)
        self._model.clear()
        for m in models:
            self._model.addItem(m)
        # Restore previous value if it's valid for this provider, else default
        if current_model in models:
            self._model.setCurrentText(current_model)
        else:
            self._model.setCurrentText(DEFAULT_MODEL[provider])
        self._model.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #

    def _load_values(self) -> None:
        # Provider
        for i, (_, val) in enumerate(PROVIDERS):
            if val == self._config.api.provider:
                self._provider.setCurrentIndex(i)
                break

        # Keys
        self._anthropic_key._field.setText(self._config.api.anthropic_api_key)  # type: ignore[attr-defined]
        self._gemini_key._field.setText(self._config.api.gemini_api_key)        # type: ignore[attr-defined]

        # Model (set after provider so list is correct)
        idx = self._model.findText(self._config.api.model)
        if idx >= 0:
            self._model.setCurrentIndex(idx)
        else:
            self._model.setCurrentText(self._config.api.model)

        self._max_tokens.setValue(self._config.api.max_tokens)

        # STT model
        idx = self._stt_model.findText(self._config.api.stt_model)
        if idx >= 0:
            self._stt_model.setCurrentIndex(idx)
        else:
            self._stt_model.setCurrentText(self._config.api.stt_model)

        # Language
        for i, (_, val) in enumerate(LANGUAGES):
            if val == self._config.api.language:
                self._language.setCurrentIndex(i)
                break

        for i, (_, val) in enumerate(SCREENSHOT_TOOLS):
            if val == self._config.hotkeys.screenshot_tool:
                self._screenshot_tool.setCurrentIndex(i)
                break
        self._hk_screenshot.setText(self._config.hotkeys.screenshot)
        self._hk_clipboard.setText(self._config.hotkeys.clipboard)
        self._width.setValue(self._config.overlay.width)
        self._height.setValue(self._config.overlay.height)
        self._opacity.setValue(self._config.overlay.opacity)
        self._font_size.setValue(self._config.overlay.font_size)
        for i, (_, val) in enumerate(THEMES):
            if val == self._config.overlay.theme:
                self._theme.setCurrentIndex(i)
                break
        self._blur_cb.setChecked(self._config.overlay.blur_enabled)
        self._blur_radius.setValue(self._config.overlay.blur_radius)
        self._blur_radius.setEnabled(self._config.overlay.blur_enabled)
        self._corner_radius.setValue(self._config.overlay.corner_radius)
        idx = self._audio_device.findData(self._config.overlay.audio_device)
        self._audio_device.setCurrentIndex(idx if idx >= 0 else 0)
        self._autostart_cb.setChecked(is_autostart_enabled())

    def _on_save(self) -> None:
        self._config.api.provider = self._current_provider()
        self._config.api.anthropic_api_key = self._anthropic_key._field.text().strip()  # type: ignore[attr-defined]
        self._config.api.gemini_api_key = self._gemini_key._field.text().strip()        # type: ignore[attr-defined]
        self._config.api.model = self._model.currentText().strip()
        self._config.api.max_tokens = self._max_tokens.value()
        self._config.api.stt_model = self._stt_model.currentText().strip()
        self._config.api.language = LANGUAGES[self._language.currentIndex()][1]

        self._config.hotkeys.screenshot_tool = SCREENSHOT_TOOLS[self._screenshot_tool.currentIndex()][1]
        self._config.hotkeys.screenshot = (
            self._hk_screenshot.text().strip() or "<ctrl>+<shift>+a"
        )
        self._config.hotkeys.clipboard = (
            self._hk_clipboard.text().strip() or "<ctrl>+<shift>+s"
        )

        self._config.overlay.width = self._width.value()
        self._config.overlay.height = self._height.value()
        self._config.overlay.opacity = self._opacity.value()
        self._config.overlay.font_size = self._font_size.value()
        self._config.overlay.theme = THEMES[self._theme.currentIndex()][1]
        self._config.overlay.blur_enabled = self._blur_cb.isChecked()
        self._config.overlay.blur_radius = self._blur_radius.value()
        self._config.overlay.corner_radius = self._corner_radius.value()
        self._config.overlay.audio_device = self._audio_device.currentData() or ""

        save_config(self._config)
        set_autostart(self._autostart_cb.isChecked())
        self.accept()
