"""Audio capture via sounddevice.

Captures audio from microphone, virtual devices, or Bluetooth HFP
using sounddevice (PortAudio).

Design:
  - Callback-based: sounddevice delivers audio chunks via a callback.
  - Device enumeration via sounddevice.query_devices().
  - Auto-fallback to MockBackend when no input devices found.
  - sounddevice import is lazy (inside methods), so CI without
    PortAudio can still import the module.

Usage:
    capture = AudioCapture()
    devices = capture.list_devices()
    capture.start(device_id=0, callback=lambda chunk: ...)
    ...
    capture.stop()
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 100  # chunk size in milliseconds
BLOCK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)  # samples per chunk


# ---------------------------------------------------------------------------
# Audio device info
# ---------------------------------------------------------------------------

class AudioDevice:
    """Represents an audio input device."""

    def __init__(self, device_id: int, name: str, channels: int, is_default: bool = False):
        self.device_id = device_id
        self.name = name
        self.channels = channels
        self.is_default = is_default

    def __repr__(self) -> str:
        return f"AudioDevice({self.device_id}, {self.name})"


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class AudioBackend(ABC):
    @abstractmethod
    def list_devices(self) -> list[AudioDevice]:
        ...

    @abstractmethod
    def start_stream(
        self,
        device_id: int,
        callback: Callable[[bytes], None],
    ) -> None:
        ...

    @abstractmethod
    def stop_stream(self) -> None:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


# ---------------------------------------------------------------------------
# sounddevice backend
# ---------------------------------------------------------------------------

class SoundDeviceBackend(AudioBackend):
    """Backend using sounddevice (PortAudio)."""

    def __init__(self):
        self._stream: Optional["sd.InputStream"] = None

    def is_available(self) -> bool:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            return any(d["max_input_channels"] > 0 for d in devices)
        except Exception:
            return False

    def list_devices(self) -> list[AudioDevice]:
        result = []
        default_id = None
        try:
            import sounddevice as sd
            default_id = sd.default.device[0]
        except Exception:
            pass

        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    result.append(AudioDevice(
                        device_id=i,
                        name=d["name"],
                        channels=d["max_input_channels"],
                        is_default=(i == default_id),
                    ))
        except Exception:
            pass
        return result

    def start_stream(
        self,
        device_id: int = 0,
        callback: Callable[[bytes], None] = lambda _: None,
    ) -> None:
        import sounddevice as sd
        import numpy as np

        def _callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            chunk = (indata * 32767).astype(np.int16).tobytes()
            callback(chunk)

        self._stream = sd.InputStream(
            device=device_id,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=BLOCK_SIZE,
            callback=_callback,
        )
        self._stream.start()

    def stop_stream(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None


# ---------------------------------------------------------------------------
# Mock backend (testing / no audio hardware)
# ---------------------------------------------------------------------------

class MockAudioBackend(AudioBackend):
    """Backend that returns mock data, no real hardware needed."""

    def __init__(self):
        self._running = False
        self._callback: Optional[Callable] = None

    def is_available(self) -> bool:
        return True

    def list_devices(self) -> list[AudioDevice]:
        return [
            AudioDevice(0, "Mock Microphone", 1, is_default=True),
            AudioDevice(1, "Mock Bluetooth HFP", 1),
        ]

    def start_stream(
        self,
        device_id: int = 0,
        callback: Callable[[bytes], None] = lambda _: None,
    ) -> None:
        self._running = True
        self._callback = callback

    def stop_stream(self) -> None:
        self._running = False
        self._callback = None

    def feed_chunk(self, data: bytes) -> None:
        """Inject mock audio data (for testing)."""
        if self._callback:
            self._callback(data)


# ---------------------------------------------------------------------------
# AudioCapture (high-level API)
# ---------------------------------------------------------------------------

class AudioCapture:
    """High-level audio capture manager."""

    def __init__(self, backend: Optional[AudioBackend] = None):
        if backend is None:
            real = SoundDeviceBackend()
            self._backend = real if real.is_available() else MockAudioBackend()
        else:
            self._backend = backend
        self._callback: Optional[Callable[[bytes], None]] = None

    def list_devices(self) -> list[AudioDevice]:
        return self._backend.list_devices()

    def start(self, device_id: int = 0) -> None:
        if self._callback is None:
            raise RuntimeError("Set a callback via on_chunk() before starting")
        self._backend.start_stream(device_id, self._callback)

    def stop(self) -> None:
        self._backend.stop_stream()

    def on_chunk(self, callback: Callable[[bytes], None]) -> None:
        self._callback = callback

    @property
    def is_mock(self) -> bool:
        return isinstance(self._backend, MockAudioBackend)
