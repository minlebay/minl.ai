# minl.ai

Lightweight system-wide AI assistant for KDE/Linux. Trigger via hotkey to analyze screen regions or selected text, powered by Anthropic Claude or Google Gemini.

![Platform](https://img.shields.io/badge/platform-Linux%20%2F%20X11-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Screenshot mode** — select any screen region with Flameshot or Spectacle, AI analyzes it
- **Clipboard / selection mode** — highlight any text, AI responds to it
- **Floating overlay** — always-on-top window with follow-up questions and retry on error
- **Voice input** — record from microphone, transcribed via Gemini STT (configurable model)
- **System tray** — lives in the tray with hotkeys; right-click for full menu
- **Session context** — follow-up questions within one overlay remember the conversation
- **Provider choice** — switch between Anthropic Claude and Google Gemini in Settings
- **Light / dark theme** — dark gray or light, switchable from Settings
- **Log viewer** — tray menu → View Logs… shows the rotating log file in-app
- **Launch at login** — one checkbox in Settings, no systemd required

## Install (recommended)

```bash
# Build the .deb package
./build_deb.sh

# Install (handles venv + all pip deps automatically)
sudo apt install ./minlai_2.3.6_all.deb
```

`postinst` creates a Python venv at `/usr/lib/minlai/venv/` and installs all dependencies via pip. No manual `pip install` needed.

Then set your API key and launch:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # or GEMINI_API_KEY for Gemini
minlai                                  # starts tray icon
```

## Quick start (from source)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
python main.py
```

## Usage

```bash
minlai                          # tray icon + hotkey daemon (default)
minlai --screenshot             # one-shot: capture region → overlay
minlai --text                   # one-shot: clipboard → overlay
minlai --screenshot --headless  # print response to terminal
minlai --text --headless
```

## Default hotkeys

| Action | Hotkey |
| --- | --- |
| Screenshot | `Ctrl+Shift+A` |
| Clipboard / selection | `Ctrl+Shift+S` |

Hotkeys are fully configurable in Settings (pynput format, e.g. `<alt>+<shift>+a`).

## Requirements

| Dependency | Purpose |
| --- | --- |
| Python 3.11+ | runtime |
| `libportaudio2` | voice recording (installed by deb) |
| `flameshot` **or** `kde-spectacle` | screenshot capture |
| `xclip` or `xsel` | clipboard reading |

PyQt6, anthropic, google-genai, pynput, sounddevice, numpy — installed automatically into the venv by `postinst`.

## Settings

Open via tray menu → **Settings…**

| Section | Option | Description |
| --- | --- | --- |
| Provider | Anthropic / Gemini | Which AI backend to use |
| API Keys | Anthropic key, Gemini key | Both stored; switch freely |
| Model | dropdown + editable | Main chat model |
| Max tokens | spinner | Response length limit |
| Voice STT model | dropdown + editable | Gemini model for transcription |
| Response language | dropdown | Auto or fixed language |
| Hotkeys | text fields | pynput format |
| Screenshot tool | Flameshot / Spectacle | Region selection tool |
| Overlay | size, opacity, font | Window appearance |
| Theme | Dark (gray) / Light | Color scheme |
| Launch at login | checkbox | Writes XDG autostart entry |

## Config file

Auto-created at `~/.config/minlai/config.toml` on first run:

```toml
[api]
provider = "anthropic"          # "anthropic" or "gemini"
# anthropic_api_key = "sk-ant-..."   # or set ANTHROPIC_API_KEY env var
# gemini_api_key    = "AIza..."      # or set GEMINI_API_KEY env var
model     = "claude-sonnet-4-6"
max_tokens = 2048
language  = "auto"
stt_model = "gemini-2.5-flash"  # used for voice transcription regardless of provider

[hotkeys]
screenshot      = "<ctrl>+<shift>+a"
clipboard       = "<ctrl>+<shift>+s"
screenshot_tool = "flameshot"   # "flameshot" or "spectacle"

[overlay]
width     = 640
height    = 480
opacity   = 0.95
font_size = 13
theme     = "dark"              # "dark" or "light"
```

## Supported models

**Anthropic:** `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001`

**Gemini (chat):** `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-1.5-flash`

**Gemini (STT):** any Gemini multimodal model — `gemini-2.5-flash` is the default. Voice transcription always uses the Gemini API key regardless of the selected main provider.

## Project structure

```text
minl.ai/
  main.py             — entry point, CLI flags, tray mode launcher
  capture.py          — flameshot/spectacle screenshot + xclip/xsel clipboard
  ai.py               — AnthropicBackend + GeminiBackend + MinlAI facade
  overlay.py          — PyQt6 floating overlay window
  tray.py             — QSystemTrayIcon, hotkey bridge, log viewer, capture worker
  settings_dialog.py  — PyQt6 settings form
  config.py           — config.toml load/save, autostart helpers
  themes.py           — dark/light color palettes + Qt stylesheet builders
  voice.py            — sounddevice recorder + Gemini transcription
  logger.py           — rotating file logger (~/.config/minlai/minlai.log)
  minlai.svg          — application icon
  requirements.txt
  build_deb.sh        — builds minlai_<version>_all.deb
  packaging/          — deb package skeleton (DEBIAN/, usr/)
```

## Notes

- Targets **X11 / XWayland** — pynput global hotkeys do not work on pure Wayland
- `DISPLAY` must be set (it is by default in any graphical session)
- Autostart uses XDG (`~/.config/autostart/minlai.desktop`), compatible with KDE, GNOME, XFCE
- Logs are written to `~/.config/minlai/minlai.log` (2 MB rotating, 1 backup)
- Voice input requires a Gemini API key even if the main provider is Anthropic

## License

MIT
