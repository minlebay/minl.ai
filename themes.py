"""Color themes for minl.ai: 'dark' (dark gray) and 'light'."""

from __future__ import annotations

# ── Palettes ──────────────────────────────────────────────────────────────────

_DARK: dict[str, str] = {
    # Backgrounds
    "window_bg":         "rgba(24, 25, 27, 0.97)",
    "surface":           "rgba(34, 36, 40, 0.90)",
    "border":            "rgba(72, 78, 88, 0.55)",
    "border_focus":      "rgba(110, 125, 145, 0.80)",
    # Text
    "text":              "#d8dde4",
    "text_dim":          "#8a96a4",
    "text_muted":        "#4e5966",
    # Buttons
    "btn":               "rgba(58, 64, 74, 0.80)",
    "btn_hover":         "rgba(74, 82, 94, 0.95)",
    "btn_send":          "rgba(52, 68, 88, 0.80)",
    "btn_send_hover":    "rgba(66, 86, 112, 0.95)",
    "btn_disabled_bg":   "rgba(40, 44, 50, 0.50)",
    "btn_disabled_text": "#4e5966",
    # Chat message labels
    "ai_color":          "#6d90a8",
    "user_color":        "#4a90c4",
    "separator":         "#3d4754",
    "thinking":          "#6d90a8",
    "error":             "#e57373",
    # Close button
    "close_hover_bg":    "rgba(200, 45, 45, 0.30)",
    "close_hover_text":  "#fca5a5",
    # Mic button
    "mic_bg":            "rgba(34, 36, 42, 0.90)",
    "mic_text":          "#6d90a8",
    "mic_border":        "rgba(72, 92, 112, 0.45)",
    "mic_hover":         "rgba(50, 60, 78, 0.85)",
    "mic_rec_bg":        "rgba(155, 28, 28, 0.88)",
    "mic_rec_border":    "#e57373",
    "mic_rec_text":      "#fecaca",
    # Title bar
    "title_icon":        "#6d90a8",
    "title_text":        "#c8d0da",
    # Retry button
    "retry_bg":          "rgba(120, 60, 30, 0.75)",
    "retry_hover":       "rgba(150, 80, 40, 0.90)",
    "retry_border":      "rgba(200, 100, 50, 0.60)",
    "retry_text":        "#fdd8b0",
    # Window opacity
    "opacity":           "0.96",
}

_LIGHT: dict[str, str] = {
    # Backgrounds
    "window_bg":         "rgba(244, 246, 250, 0.97)",
    "surface":           "rgba(255, 255, 255, 0.95)",
    "border":            "rgba(175, 185, 200, 0.55)",
    "border_focus":      "rgba(65, 100, 155, 0.65)",
    # Text
    "text":              "#18202e",
    "text_dim":          "#44557a",
    "text_muted":        "#7a8898",
    # Buttons
    "btn":               "rgba(38, 52, 72, 0.90)",
    "btn_hover":         "rgba(22, 36, 56, 0.97)",
    "btn_send":          "rgba(38, 52, 72, 0.90)",
    "btn_send_hover":    "rgba(22, 36, 56, 0.97)",
    "btn_disabled_bg":   "rgba(190, 198, 210, 0.55)",
    "btn_disabled_text": "#8898aa",
    # Chat message labels
    "ai_color":          "#1e4a78",
    "user_color":        "#1454aa",
    "separator":         "#b8c4d2",
    "thinking":          "#4070a0",
    "error":             "#c0392b",
    # Close button
    "close_hover_bg":    "rgba(200, 30, 30, 0.12)",
    "close_hover_text":  "#b02020",
    # Mic button
    "mic_bg":            "rgba(238, 242, 250, 0.95)",
    "mic_text":          "#1e4a78",
    "mic_border":        "rgba(140, 162, 192, 0.55)",
    "mic_hover":         "rgba(218, 228, 244, 0.95)",
    "mic_rec_bg":        "rgba(190, 28, 28, 0.88)",
    "mic_rec_border":    "#e74c3c",
    "mic_rec_text":      "#fff5f5",
    # Title bar
    "title_icon":        "#1e4a78",
    "title_text":        "#18202e",
    # Retry button
    "retry_bg":          "rgba(180, 80, 20, 0.80)",
    "retry_hover":       "rgba(200, 100, 30, 0.95)",
    "retry_border":      "rgba(200, 100, 40, 0.55)",
    "retry_text":        "#fff0e0",
    # Window opacity
    "opacity":           "0.97",
}

PALETTES: dict[str, dict[str, str]] = {"dark": _DARK, "light": _LIGHT}


def get(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, _DARK)


# ── Stylesheet builders ───────────────────────────────────────────────────────

def overlay_style(fs: int, theme: str = "dark") -> str:
    c = get(theme)
    return f"""
        QWidget#central {{
            background: {c['window_bg']};
            border: 1px solid {c['border']};
            border-radius: 12px;
        }}
        QWidget#titleBar {{ background: transparent; }}
        QLabel#titleIcon {{
            color: {c['title_icon']};
            font-size: {fs + 4}px;
            font-weight: bold;
            padding-right: 4px;
        }}
        QLabel#titleLabel {{
            color: {c['title_text']};
            font-size: {fs + 2}px;
            font-weight: bold;
            letter-spacing: 1px;
        }}
        QPushButton#closeBtn {{
            background: transparent;
            color: {c['text_dim']};
            border: none;
            font-size: {fs}px;
            border-radius: 4px;
        }}
        QPushButton#closeBtn:hover {{
            background: {c['close_hover_bg']};
            color: {c['close_hover_text']};
        }}
        QTextEdit#chat {{
            background: transparent;
            color: {c['text']};
            border: none;
            font-size: {fs}px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            selection-background-color: rgba(80, 110, 160, 0.30);
        }}
        QLineEdit#inputField {{
            background: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: {fs}px;
        }}
        QLineEdit#inputField:focus {{
            border-color: {c['border_focus']};
        }}
        QPushButton#sendBtn {{
            background: {c['btn_send']};
            color: {'#f0f4f8' if theme == 'dark' else '#f0f4f8'};
            border: none;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: {fs}px;
            font-weight: bold;
        }}
        QPushButton#sendBtn:hover  {{ background: {c['btn_send_hover']}; }}
        QPushButton#sendBtn:disabled {{
            background: {c['btn_disabled_bg']};
            color: {c['btn_disabled_text']};
        }}
        QPushButton#retryBtn {{
            background: {c['retry_bg']};
            color: {c['retry_text']};
            border: 1px solid {c['retry_border']};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: {fs}px;
            font-weight: bold;
        }}
        QPushButton#retryBtn:hover {{ background: {c['retry_hover']}; }}
        QPushButton#micBtn {{
            background: {c['mic_bg']};
            color: {c['mic_text']};
            border: 1px solid {c['mic_border']};
            border-radius: 6px;
            font-size: {fs + 2}px;
            padding: 0;
        }}
        QPushButton#micBtn:hover {{ background: {c['mic_hover']}; border-color: {c['border_focus']}; }}
        QPushButton#micBtn[recording="true"] {{
            background: {c['mic_rec_bg']};
            border-color: {c['mic_rec_border']};
            color: {c['mic_rec_text']};
        }}
        QPushButton#micBtn:disabled {{
            background: {c['btn_disabled_bg']};
            color: {c['btn_disabled_text']};
            border-color: {c['border']};
        }}
    """


def dialog_style(theme: str = "dark") -> str:
    c = get(theme)
    # URL-encode '#' for inline SVG data URI
    arrow_color = c['text_dim'].replace('#', '%23')
    arrow = (
        f"data:image/svg+xml;utf8,"
        f"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'>"
        f"<polygon points='0,0 10,0 5,6' fill='{arrow_color}'/>"
        f"</svg>"
    )
    return f"""
        QDialog {{ background: {c['window_bg']}; color: {c['text']}; }}
        QGroupBox {{
            color: {c['title_icon']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            margin-top: 8px; padding-top: 8px;
            font-weight: bold;
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
        QLabel {{ color: {c['text_dim']}; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 5px; padding: 4px 8px;
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {c['border_focus']};
        }}
        QLineEdit:disabled {{ color: {c['text_muted']}; border-color: {c['border']}; }}
        QPushButton {{
            background: {c['btn']};
            color: #f0f4f8;
            border: none; border-radius: 5px; padding: 5px 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background: {c['btn_hover']}; }}
        QPushButton:flat {{ background: {c['surface']}; color: {c['text_dim']}; }}
        QDialogButtonBox QPushButton {{ min-width: 70px; }}
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            background: {c['surface']}; border: none;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border-left: 1px solid {c['border']};
            border-top-right-radius: 5px;
            border-bottom-right-radius: 5px;
        }}
        QComboBox::down-arrow {{
            image: url("{arrow}");
            width: 10px;
            height: 6px;
        }}
        QComboBox QAbstractItemView {{
            background: {c['surface']}; color: {c['text']};
            selection-background-color: rgba(80, 110, 160, 0.35);
        }}
        QCheckBox {{ color: {c['text_dim']}; spacing: 8px; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border: 1px solid {c['border']};
            border-radius: 3px; background: {c['surface']};
        }}
        QCheckBox::indicator:checked {{ background: {c['btn_send']}; }}
        QCheckBox::indicator:hover {{ border-color: {c['border_focus']}; }}
    """
