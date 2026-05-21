"""Claude and Gemini API backends with a unified OrbitAI facade."""

from __future__ import annotations

import base64
from typing import Optional

from config import Config, PROVIDER_GEMINI


# ── Anthropic backend ─────────────────────────────────────────────────────────

class _AnthropicBackend:
    def __init__(self, config: Config) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.api.anthropic_api_key)
        self._model = config.api.model
        self._max_tokens = config.api.max_tokens
        # History in Anthropic message format
        self._history: list[dict] = []

    def reset(self) -> None:
        self._history.clear()

    @property
    def has_context(self) -> bool:
        return bool(self._history)

    def send_text(self, text: str, system: str = "") -> str:
        self._history.append({"role": "user", "content": text})
        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": self._history,
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        reply = response.content[0].text
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def send_image(self, image_bytes: bytes, prompt: str = "", system: str = "") -> str:
        b64 = base64.standard_b64encode(image_bytes).decode()
        content: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            },
            {
                "type": "text",
                "text": prompt or "What do you see in this screenshot? Describe it concisely and helpfully.",
            },
        ]
        self._history.append({"role": "user", "content": content})
        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": self._history,
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        reply = response.content[0].text
        self._history.append({"role": "assistant", "content": reply})
        return reply


# ── Gemini backend ────────────────────────────────────────────────────────────

class _GeminiBackend:
    def __init__(self, config: Config) -> None:
        # Client is created lazily on first use so an empty key doesn't crash at startup
        self._api_key = config.api.gemini_api_key
        self._model = config.api.model
        self._max_tokens = config.api.max_tokens
        self._client = None
        self._chat = None

    def reset(self) -> None:
        self._chat = None

    @property
    def has_context(self) -> bool:
        return self._chat is not None

    def _get_chat(self, system: str = ""):
        if self._chat is None:
            from google import genai
            from google.genai import types
            if self._client is None:
                self._client = genai.Client(api_key=self._api_key)
            cfg = types.GenerateContentConfig(
                max_output_tokens=self._max_tokens,
                **({"system_instruction": system} if system else {}),
            )
            self._chat = self._client.chats.create(model=self._model, config=cfg)
        return self._chat

    def send_text(self, text: str, system: str = "") -> str:
        chat = self._get_chat(system)
        response = chat.send_message(text)
        return response.text

    def send_image(self, image_bytes: bytes, prompt: str = "", system: str = "") -> str:
        from google.genai import types
        chat = self._get_chat(system)
        parts = [
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png",
            ),
            prompt or "What do you see in this screenshot? Describe it concisely and helpfully.",
        ]
        response = chat.send_message(parts)
        return response.text


# ── Public facade ─────────────────────────────────────────────────────────────

class OrbitAI:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._backend = self._make_backend()

    def _make_backend(self) -> _AnthropicBackend | _GeminiBackend:
        if self._config.api.provider == PROVIDER_GEMINI:
            return _GeminiBackend(self._config)
        return _AnthropicBackend(self._config)

    def reload(self) -> None:
        """Recreate backend after config changes (new key, provider, or model)."""
        self._backend = self._make_backend()

    def reset_session(self) -> None:
        self._backend.reset()

    def _full_system(self, base: str = "") -> str:
        """Append language instruction to any system prompt."""
        lang = self._config.api.language
        if lang and lang != "auto":
            suffix = f"Always respond in {lang}, regardless of the language of the input."
            return f"{base}\n{suffix}".strip() if base else suffix
        return base

    def ask_text(self, text: str, system: str = "") -> str:
        return self._backend.send_text(text, self._full_system(system))

    def ask_screenshot(self, image_bytes: bytes, prompt: str = "") -> str:
        return self._backend.send_image(image_bytes, prompt, self._full_system())

    def follow_up(self, question: str) -> str:
        return self._backend.send_text(question)

    @property
    def has_context(self) -> bool:
        return self._backend.has_context
