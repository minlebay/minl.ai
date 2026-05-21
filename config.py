"""Config loading from ~/.config/minlai/config.toml with env var fallbacks."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

CONFIG_DIR = Path.home() / ".config" / "minlai"
CONFIG_FILE = CONFIG_DIR / "config.toml"
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "minlai.desktop"

_AUTOSTART_CONTENT = """\
[Desktop Entry]
Type=Application
Name=minl.ai
Exec=minlai --tray
Icon=minlai
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=minl.ai desktop assistant
"""

DEFAULT_CONFIG_TOML = """\
[api]
provider = "anthropic"
# anthropic_api_key = "sk-ant-..."
# gemini_api_key    = "AIza..."
model = "claude-sonnet-4-6"
max_tokens = 2048
language = "auto"
stt_model = "gemini-2.5-flash"

[hotkeys]
screenshot      = "<ctrl>+<shift>+a"
clipboard       = "<ctrl>+<shift>+s"
screenshot_tool = "flameshot"

[overlay]
width     = 640
height    = 480
opacity   = 0.95
font_size = 13
theme     = "dark"
"""

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"

DEFAULT_MODEL: dict[str, str] = {
    PROVIDER_ANTHROPIC: "claude-sonnet-4-6",
    PROVIDER_GEMINI: "gemini-2.5-flash",
}


@dataclass
class ApiConfig:
    provider: str = PROVIDER_ANTHROPIC
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2048
    language: str = "auto"
    stt_model: str = "gemini-2.5-flash"


@dataclass
class HotkeysConfig:
    screenshot: str = "<ctrl>+<shift>+a"
    clipboard: str = "<ctrl>+<shift>+s"
    screenshot_tool: str = "flameshot"


@dataclass
class OverlayConfig:
    width: int = 640
    height: int = 480
    opacity: float = 0.95
    font_size: int = 13
    theme: str = "dark"


@dataclass
class Config:
    api: ApiConfig = field(default_factory=ApiConfig)
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)


# ── Autostart ─────────────────────────────────────────────────────────────────

def is_autostart_enabled() -> bool:
    return AUTOSTART_FILE.exists()


def set_autostart(enabled: bool) -> None:
    if enabled:
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(_AUTOSTART_CONTENT)
    else:
        AUTOSTART_FILE.unlink(missing_ok=True)


# ── Persistence ───────────────────────────────────────────────────────────────

def _ensure_default_config() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG_TOML)


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "[api]",
        f'provider = "{config.api.provider}"',
    ]
    if config.api.anthropic_api_key:
        lines.append(f'anthropic_api_key = "{config.api.anthropic_api_key}"')
    if config.api.gemini_api_key:
        lines.append(f'gemini_api_key    = "{config.api.gemini_api_key}"')
    lines += [
        f'model = "{config.api.model}"',
        f"max_tokens = {config.api.max_tokens}",
        f'language = "{config.api.language}"',
        f'stt_model = "{config.api.stt_model}"',
        "",
        "[hotkeys]",
        f'screenshot      = "{config.hotkeys.screenshot}"',
        f'clipboard       = "{config.hotkeys.clipboard}"',
        f'screenshot_tool = "{config.hotkeys.screenshot_tool}"',
        "",
        "[overlay]",
        f"width     = {config.overlay.width}",
        f"height    = {config.overlay.height}",
        f"opacity   = {config.overlay.opacity}",
        f"font_size = {config.overlay.font_size}",
        f'theme     = "{config.overlay.theme}"',
        "",
    ]
    CONFIG_FILE.write_text("\n".join(lines))


def load_config() -> Config:
    _ensure_default_config()

    raw: dict = {}
    if tomllib is not None and CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            raw = tomllib.load(f)

    api_raw = raw.get("api", {})
    hotkeys_raw = raw.get("hotkeys", {})
    overlay_raw = raw.get("overlay", {})

    provider = api_raw.get("provider", PROVIDER_ANTHROPIC)
    anthropic_key = (
        os.environ.get("ANTHROPIC_API_KEY") or api_raw.get("anthropic_api_key", "")
    )
    gemini_key = (
        os.environ.get("GEMINI_API_KEY") or api_raw.get("gemini_api_key", "")
    )
    default_model = DEFAULT_MODEL.get(provider, DEFAULT_MODEL[PROVIDER_ANTHROPIC])

    return Config(
        api=ApiConfig(
            provider=provider,
            anthropic_api_key=anthropic_key,
            gemini_api_key=gemini_key,
            model=api_raw.get("model", default_model),
            max_tokens=int(api_raw.get("max_tokens", 2048)),
            language=api_raw.get("language", "auto"),
            stt_model=api_raw.get("stt_model", "gemini-2.5-flash"),
        ),
        hotkeys=HotkeysConfig(
            screenshot=hotkeys_raw.get("screenshot", "<ctrl>+<shift>+a"),
            clipboard=hotkeys_raw.get("clipboard", "<ctrl>+<shift>+s"),
            screenshot_tool=hotkeys_raw.get("screenshot_tool", "flameshot"),
        ),
        overlay=OverlayConfig(
            width=int(overlay_raw.get("width", 640)),
            height=int(overlay_raw.get("height", 480)),
            opacity=float(overlay_raw.get("opacity", 0.95)),
            font_size=int(overlay_raw.get("font_size", 13)),
            theme=overlay_raw.get("theme", "dark"),
        ),
    )
