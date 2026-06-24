"""Audio capture via PulseAudio.

Captures audio from microphone, virtual devices, or Bluetooth HFP
using PulseAudio's `parec` command-line tool.

Design:
  - Subprocess-based: spawns `parec` and reads PCM audio from stdout.
  - Chunked callback: audio data is delivered in fixed-size chunks.
  - Device enumeration via `pactl list sources`.
  - Graceful fallback when no audio hardware is available.

Usage:
    capture = AudioCapture()
    devices = capture.list_devices()
    capture.start(device_name="default", callback=lambda chunk: ...)
    ...
    capture.stop()
"""

from __future__ import annotations

import json
import subprocess
import shutil
from abc import ABC, abstractmethod
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM
CHUNK_MS = 100    # chunk size in milliseconds
CHUNK_SIZE = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * CHUNK_MS / 1000)


# ---------------------------------------------------------------------------
# Audio device info
# ---------------------------------------------------------------------------

class AudioDevice:
    """Represents an audio input device."""

    def __init__(self, name: str, description: str, is_monitor: bool = False):
        self.name = name
        self.description = description
        self.is_monitor = is_monitor

    def __repr__(self) -> str:
        return f"AudioDevice({self.name}, {self.description})"


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class AudioBackend(ABC):
    """Abstract audio capture backend."""

    @abstractmethod
    def list_devices(self) -> list[AudioDevice]:
        """List available audio input sources."""
        ...

    @abstractmethod
    def start_stream(
        self,
        device_name: str,
        callback: Callable[[bytes], None],
    ) -> None:
        """Start capturing from a device.

        Args:
            device_name: PulseAudio source name.
            callback: Called with each PCM audio chunk (bytes).
        """
        ...

    @abstractmethod
    def stop_stream(self) -> None:
        """Stop capturing."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if PulseAudio is available on this system."""
        ...


# ---------------------------------------------------------------------------
# PulseAudio backend (production)
# ---------------------------------------------------------------------------

class PulseAudioBackend(AudioBackend):
    """Backend using PulseAudio's parec and pactl commands."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        return shutil.which("parec") is not None and shutil.which("pactl") is not None

    def list_devices(self) -> list[AudioDevice]:
        if not self.is_available():
            return []

        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "--format=json"],
                capture_output=True, text=True, timeout=5,
            )
            devices = []
            for src in json.loads(result.stdout):
                name = src.get("name", "")
                desc = src.get("description", name)
                is_mon = src.get("monitor_of_source") is not None
                devices.append(AudioDevice(name, desc, is_mon))
            return devices
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return []

    def start_stream(
        self,
        device_name: str = "@DEFAULT_SOURCE@",
        callback: Callable[[bytes], None] = lambda _: None,
    ) -> None:
        if not self.is_available():
            raise RuntimeError("PulseAudio is not available on this system")

        cmd = [
            "parec",
            f"--device={device_name}",
            f"--rate={SAMPLE_RATE}",
            f"--channels={CHANNELS}",
            f"--format=s16le",
            "--raw",
        ]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # Read loop in current thread — caller should run in a background thread
        while self._process and self._process.poll() is None:
            chunk = self._process.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            callback(chunk)

    def stop_stream(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None


# ---------------------------------------------------------------------------
# Mock backend (testing / development without audio hardware)
# ---------------------------------------------------------------------------

class MockAudioBackend(AudioBackend):
    """Backend that returns mock data, no real hardware needed."""

    def __init__(self):
        self._running = False
        self._recorded_chunks: list[bytes] = []
        self._devices = [
            AudioDevice("alsa_input.pci-0000_00_1f.3.analog-stereo", "Built-in Microphone"),
            AudioDevice("bluez_source.xx_xx_xx_xx_xx_xx", "Bluetooth HFP (Phone)"),
        ]

    def is_available(self) -> bool:
        return True

    def list_devices(self) -> list[AudioDevice]:
        return self._devices

    def start_stream(
        self,
        device_name: str = "default",
        callback: Callable[[bytes], None] = lambda _: None,
    ) -> None:
        self._running = True
        # In mock mode, just store the device name and callback
        self._device = device_name
        self._callback = callback

    def stop_stream(self) -> None:
        self._running = False

    def feed_chunk(self, data: bytes) -> None:
        """Inject mock audio data (for testing)."""
        if self._callback:
            self._callback(data)


# ---------------------------------------------------------------------------
# AudioCapture (high-level API)
# ---------------------------------------------------------------------------

class AudioCapture:
    """High-level audio capture manager.

    Automatically selects PulseAudio backend when available,
    falls back to mock backend in development/testing.
    """

    def __init__(self, backend: Optional[AudioBackend] = None):
        if backend is None:
            real = PulseAudioBackend()
            self._backend = real if real.is_available() else MockAudioBackend()
        else:
            self._backend = backend
        self._callback: Optional[Callable[[bytes], None]] = None

    def list_devices(self) -> list[AudioDevice]:
        """List available audio input sources."""
        return self._backend.list_devices()

    def start(self, device_name: str = "@DEFAULT_SOURCE@") -> None:
        """Start capturing audio.

        Captured chunks are delivered via the callback set by ``on_chunk()``.
        """
        if self._callback is None:
            raise RuntimeError("Set a callback via on_chunk() before starting")
        self._backend.start_stream(device_name, self._callback)

    def stop(self) -> None:
        """Stop capturing."""
        self._backend.stop_stream()

    def on_chunk(self, callback: Callable[[bytes], None]) -> None:
        """Register a callback for audio chunks."""
        self._callback = callback

    @property
    def is_mock(self) -> bool:
        """True if no real audio hardware was found."""
        return isinstance(self._backend, MockAudioBackend)
