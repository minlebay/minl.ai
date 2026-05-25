"""Color themes for minl.ai: 'dark' (dark gray) and 'light'."""

from __future__ import annotations

import os


def _write_svg(svg: str, name: str) -> str:
    """Write SVG to /tmp/minlai_{name}.svg — Qt can reference it in url()."""
    path = f"/tmp/minlai_{name}.svg"
    try:
        with open(path, "w") as f:
            f.write(svg)
    except OSError:
        pass
    return path

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
    "mic_text":          "#aabfcc",
    "mic_border":        "rgba(80, 105, 130, 0.55)",
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
    # Blur-mode: semi-transparent color overlay drawn on top of blurred desktop
    "blur_overlay":      "rgba(20, 22, 25, 0.72)",
}

_LIGHT: dict[str, str] = {
    # Backgrounds
    "window_bg":         "rgba(245, 248, 255, 0.93)",
    "surface":           "rgba(255, 255, 255, 0.95)",
    "border":            "rgba(148, 162, 185, 0.80)",
    "border_focus":      "rgba(55, 95, 160, 0.90)",
    # Text
    "text":              "#18202e",
    "text_dim":          "#3a4e6a",
    "text_muted":        "#6a7a8e",
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
    "separator":         "#a0aec0",
    "thinking":          "#4070a0",
    "error":             "#c0392b",
    # Close button
    "close_hover_bg":    "rgba(200, 30, 30, 0.12)",
    "close_hover_text":  "#b02020",
    # Mic button
    "mic_bg":            "rgba(228, 235, 248, 0.95)",
    "mic_text":          "#1a2d44",
    "mic_border":        "rgba(118, 142, 175, 0.75)",
    "mic_hover":         "rgba(210, 222, 242, 0.98)",
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
    # Blur-mode: semi-transparent color overlay drawn on top of blurred desktop
    "blur_overlay":      "rgba(232, 238, 250, 0.75)",
}

PALETTES: dict[str, dict[str, str]] = {"dark": _DARK, "light": _LIGHT}


def get(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, _DARK)


# ── Stylesheet builders ───────────────────────────────────────────────────────

def overlay_style(fs: int, theme: str = "dark", blur_bg: bool = False) -> str:
    c = get(theme)
    central_bg = c['blur_overlay'] if blur_bg else c['window_bg']
    return f"""
        QWidget#central {{
            background: {central_bg};
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
            padding: 6px 8px;
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
    _td = c['text_dim']
    arrow = _write_svg(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'>"
        f"<polygon points='0,0 10,0 5,6' fill='{_td}'/>"
        f"</svg>",
        f"arrow_{theme}"
    )
    check = _write_svg(
        "<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12'>"
        "<polyline points='2,7 5,10 10,3' stroke='#ffffff' stroke-width='2.2' "
        "fill='none' stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>",
        "check"
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
        QCheckBox::indicator:checked {{
            background: {c['btn_send_hover']};
            border-color: {c['border_focus']};
            image: url("{check}");
        }}
        QCheckBox::indicator:hover {{ border-color: {c['border_focus']}; }}
    """
