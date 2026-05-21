"""Voice recording (sounddevice) and transcription (Gemini API)."""

from __future__ import annotations

import io
import wave
from typing import Optional

from config import Config


# ── Availability check ────────────────────────────────────────────────────────

def sounddevice_available() -> bool:
    try:
        import sounddevice  # noqa: F401
        import numpy        # noqa: F401
        return True
    except ImportError:
        return False


# ── Recorder ──────────────────────────────────────────────────────────────────

def _get_input_samplerate() -> int:
    """Return the default input device's native sample rate."""
    import sounddevice as sd
    try:
        info = sd.query_devices(kind="input")
        rate = int(info["default_samplerate"])
        return rate if rate > 0 else 44_100
    except Exception:
        return 44_100


class VoiceRecorder:
    """Non-blocking microphone recorder. Call start(), then stop() → WAV bytes."""

    def __init__(self) -> None:
        self._chunks: list = []
        self._stream = None
        self._samplerate: int = 16_000  # updated in start()

    def start(self) -> None:
        import sounddevice as sd
        self._chunks = []
        self._samplerate = _get_input_samplerate()
        self._stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time, status) -> None:
        self._chunks.append(indata.copy())

    def stop(self) -> bytes:
        """Stop recording and return WAV bytes. Safe to call if not started."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._chunks:
            return b""
        import numpy as np
        audio = np.concatenate(self._chunks, axis=0)
        return _to_wav(audio, self._samplerate)

    @property
    def is_recording(self) -> bool:
        return self._stream is not None and self._stream.active


# ── WAV helper ────────────────────────────────────────────────────────────────

def _to_wav(audio, samplerate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # int16 = 2 bytes per sample
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, config: Config) -> str:
    """Send WAV bytes to Gemini and return transcribed text.

    Always uses Gemini regardless of the current AI provider,
    because Anthropic has no speech-to-text endpoint.
    Requires config.api.gemini_api_key to be set.
    """
    if not config.api.gemini_api_key:
        raise RuntimeError(
            "Voice input requires a Gemini API key.\n"
            "Add it in tray → Settings → Gemini Key."
        )

    from google import genai
    from google.genai import types

    model = config.api.stt_model or "gemini-2.5-flash"
    client = genai.Client(api_key=config.api.gemini_api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
            (
                "Transcribe the speech in this audio recording. "
                "Return only the transcribed text, nothing else. "
                "If there is no speech, return an empty string."
            ),
        ],
    )
    return response.text.strip()
