"""Voice recording (parecord primary / sounddevice fallback) and Gemini transcription."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import wave
from typing import Optional

import logger as _log

_logger = _log.get("voice")


# ── Device enumeration ────────────────────────────────────────────────────────

def list_audio_devices() -> list[tuple[str, str]]:
    """Return [(display_name, source_name)] via pactl, excluding monitor sources."""
    try:
        r = subprocess.run(
            ["pactl", "--format=json", "list", "sources"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if r.returncode == 0:
            return [
                (s.get("description") or s["name"], s["name"])
                for s in json.loads(r.stdout)
                if not s.get("name", "").endswith(".monitor")
            ]
    except Exception:
        pass
    # Text-format fallback
    try:
        r = subprocess.run(
            ["pactl", "list", "sources"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if r.returncode == 0:
            result, name, desc = [], None, None
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("Description:"):
                    desc = line.split(":", 1)[1].strip()
                    if name and not name.endswith(".monitor"):
                        result.append((desc or name, name))
                    name = desc = None
            return result
    except Exception:
        pass
    return []


# ── Mute check ────────────────────────────────────────────────────────────────

def is_muted(source: str = "") -> bool:
    """Return True if the PulseAudio source is muted. Returns False on any error."""
    try:
        target = source if source else "@DEFAULT_SOURCE@"
        r = subprocess.run(
            ["pactl", "get-source-mute", target],
            capture_output=True, text=True, timeout=2, check=False,
        )
        return r.returncode == 0 and "yes" in r.stdout.lower()
    except Exception:
        return False


# ── Availability checks ───────────────────────────────────────────────────────

def _parecord_available() -> bool:
    try:
        return subprocess.run(
            ["which", "parecord"], capture_output=True, timeout=2
        ).returncode == 0
    except Exception:
        return False


def sounddevice_available() -> bool:
    try:
        import sounddevice  # noqa: F401
        import numpy        # noqa: F401
        return True
    except ImportError:
        return False


def voice_input_available() -> bool:
    return _parecord_available() or sounddevice_available()


# ── Recorder ──────────────────────────────────────────────────────────────────

class VoiceRecorder:
    """
    Non-blocking recorder. Tries parecord (PulseAudio) first, falls back to sounddevice.
    On device failure, retries with the system default automatically.
    """

    def __init__(self, device: str = "") -> None:
        """device: PulseAudio source name from list_audio_devices(), or '' for default."""
        self._device = device
        self._backend = "none"
        # parecord state
        self._process: Optional[subprocess.Popen] = None
        self._tmpfile_path: Optional[str] = None
        # sounddevice state
        self._sd_chunks: list = []
        self._sd_stream = None
        self._sd_samplerate: int = 16_000

    @property
    def is_recording(self) -> bool:
        if self._backend == "parecord":
            return self._process is not None and self._process.poll() is None
        if self._backend == "sounddevice":
            return self._sd_stream is not None and self._sd_stream.active
        return False

    def start(self) -> None:
        self._reset()
        if _parecord_available():
            self._start_parecord(self._device)
        elif sounddevice_available():
            self._start_sounddevice()
        else:
            raise RuntimeError(
                "No recording backend available.\n"
                "Install pulseaudio-utils (parecord) or sounddevice."
            )

    def _start_parecord(self, device: str, _retry: bool = True) -> None:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        self._tmpfile_path = path
        cmd = [
            "parecord",
            "--rate=16000", "--format=s16le",
            "--channels=1", "--file-format=wav",
            "--latency-msec=100",
        ]
        if device:
            cmd.append(f"--device={device}")
        cmd.append(path)
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._backend = "parecord"
            _logger.debug("parecord started (device=%r)", device or "default")
        except Exception as exc:
            _logger.warning("parecord failed (device=%r): %s", device, exc)
            # Clean up temp file before retry
            try:
                os.unlink(path)
            except Exception:
                pass
            self._tmpfile_path = None
            if device and _retry:
                _logger.info("Retrying parecord with system default")
                self._start_parecord("", _retry=False)
            else:
                raise

    def _start_sounddevice(self) -> None:
        import sounddevice as sd
        self._sd_chunks = []
        try:
            info = sd.query_devices(kind="input") or {}
            rate = int(info.get("default_samplerate", 44_100))
        except Exception:
            rate = 44_100
        self._sd_samplerate = rate if rate > 0 else 44_100

        def _cb(indata, frames, time, status):
            self._sd_chunks.append(indata.copy())

        self._sd_stream = sd.InputStream(
            samplerate=self._sd_samplerate, channels=1, dtype="int16", callback=_cb
        )
        self._sd_stream.start()
        self._backend = "sounddevice"
        _logger.debug("sounddevice recording started")

    def stop(self) -> bytes:
        """Stop recording; return WAV bytes (empty bytes if nothing captured)."""
        if self._backend == "parecord":
            return self._stop_parecord()
        if self._backend == "sounddevice":
            return self._stop_sounddevice()
        return b""

    def _stop_parecord(self) -> bytes:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None
        data = b""
        if self._tmpfile_path:
            try:
                with open(self._tmpfile_path, "rb") as f:
                    data = f.read()
            except Exception as exc:
                _logger.error("Failed reading parecord output: %s", exc)
            try:
                os.unlink(self._tmpfile_path)
            except Exception:
                pass
            self._tmpfile_path = None
        return data

    def _stop_sounddevice(self) -> bytes:
        if self._sd_stream:
            self._sd_stream.stop()
            self._sd_stream.close()
            self._sd_stream = None
        if not self._sd_chunks:
            return b""
        import numpy as np
        audio = np.concatenate(self._sd_chunks, axis=0)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sd_samplerate)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()

    def _reset(self) -> None:
        self._sd_chunks = []
        self._sd_stream = None
        self._process = None
        self._tmpfile_path = None
        self._backend = "none"


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, config) -> str:
    """Send WAV bytes to Gemini STT. Always uses Gemini regardless of main provider."""
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
    return (response.text or "").strip()
