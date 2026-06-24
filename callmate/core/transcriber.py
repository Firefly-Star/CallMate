"""Speech-to-text via Deepgram real-time API.

Receives audio chunks from AudioCapture, sends them to Deepgram,
and delivers real-time transcription results with speaker diarization.

Usage:
    transcriber = Transcriber(api_key="...")
    transcriber.on_transcript(lambda text, speaker, is_final: ...)
    transcriber.on_utterance(lambda text, speaker: ...)
    transcriber.start()
    transcriber.send_audio(chunk)   # called repeatedly
    transcriber.stop()
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
ENCODING = "linear16"

# Map Deepgram speaker IDs to our roles
SPEAKER_MAP = {0: "other", 1: "user"}


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class TranscriberBackend(ABC):
    """Abstract STT backend."""

    @abstractmethod
    def start(self) -> None:
        """Open connection to STT service."""
        ...

    @abstractmethod
    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk for transcription."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Close connection."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...


# ---------------------------------------------------------------------------
# Deepgram backend
# ---------------------------------------------------------------------------

class DeepgramBackend(TranscriberBackend):
    """Backend using Deepgram's real-time WebSocket API."""

    def __init__(
        self,
        api_key: str,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
    ):
        self._api_key = api_key
        self._sample_rate = sample_rate
        self._channels = channels
        self._socket: Optional["WebSocket"] = None
        self._on_transcript: Optional[Callable] = None
        self._on_utterance: Optional[Callable] = None

    def set_callbacks(
        self,
        on_transcript: Optional[Callable[[str, int, bool], None]] = None,
        on_utterance: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self._on_transcript = on_transcript
        self._on_utterance = on_utterance

    def start(self) -> None:
        import websockets.sync.client

        url = self._build_url()
        self._socket = websockets.sync.client.connect(url)

        # Start a listener thread for incoming messages
        self._listener_thread = threading.Thread(target=self._listen, daemon=True)
        self._listener_thread.start()

    def send_audio(self, chunk: bytes) -> None:
        if self._socket:
            try:
                self._socket.send(chunk)
            except Exception:
                pass

    def stop(self) -> None:
        if self._socket:
            # Send close message
            try:
                self._socket.send(json.dumps({"type": "CloseStream"}))
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def is_connected(self) -> bool:
        return self._socket is not None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_url(self) -> str:
        params = {
            "encoding": ENCODING,
            "sample_rate": self._sample_rate,
            "channels": self._channels,
            "model": "nova-2",
            "smart_format": "true",
            "diarize": "true",
            "endpointing": "200",
            "utterance_end_ms": "1000",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"wss://api.deepgram.com/v1/listen?{query}"

    def _listen(self) -> None:
        """Background thread: read messages from Deepgram."""
        import websockets

        while self._socket:
            try:
                message = self._socket.recv()
                if isinstance(message, bytes):
                    continue
                self._handle_message(json.loads(message))
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception:
                break

    def _handle_message(self, data: dict) -> None:
        msg_type = data.get("type", "")

        if msg_type == "Results":
            self._handle_results(data)
        elif msg_type == "UtteranceEnd":
            self._handle_utterance_end(data)

    def _handle_results(self, data: dict) -> None:
        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])
        if not alternatives:
            return

        alt = alternatives[0]
        transcript = alt.get("transcript", "").strip()
        if not transcript:
            return

        is_final = data.get("is_final", False)
        # Get speaker from the first word
        words = alt.get("words", [])
        speaker = words[0].get("speaker", 0) if words else 0

        if self._on_transcript:
            self._on_transcript(transcript, speaker, is_final)

    def _handle_utterance_end(self, data: dict) -> None:
        transcript = data.get("transcript", "").strip()
        speaker = data.get("speaker", 0)
        if transcript and self._on_utterance:
            self._on_utterance(transcript, speaker)


# ---------------------------------------------------------------------------
# Mock backend (for testing without API key)
# ---------------------------------------------------------------------------

class MockTranscriberBackend(TranscriberBackend):
    """Mock backend that returns canned transcripts."""

    def __init__(self):
        self._connected = False
        self._on_transcript: Optional[Callable] = None
        self._on_utterance: Optional[Callable] = None
        self._received_chunks: list[bytes] = []

    def set_callbacks(
        self,
        on_transcript: Optional[Callable[[str, int, bool], None]] = None,
        on_utterance: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self._on_transcript = on_transcript
        self._on_utterance = on_utterance

    def start(self) -> None:
        self._connected = True

    def send_audio(self, chunk: bytes) -> None:
        self._received_chunks.append(chunk)

    def stop(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def inject_transcript(self, text: str, speaker: int = 0, is_final: bool = True) -> None:
        """Simulate a transcript result (for testing)."""
        if self._on_transcript:
            self._on_transcript(text, speaker, is_final)

    def inject_utterance(self, text: str, speaker: int = 0) -> None:
        """Simulate an utterance end event."""
        if self._on_utterance:
            self._on_utterance(text, speaker)


# ---------------------------------------------------------------------------
# High-level Transcriber
# ---------------------------------------------------------------------------

class Transcriber:
    """High-level STT manager.

    Automatically selects Deepgram backend when API key is provided,
    falls back to Mock backend otherwise.
    """

    def __init__(self, backend: Optional[TranscriberBackend] = None):
        self._backend = backend or MockTranscriberBackend()

    def on_transcript(self, callback: Callable[[str, str, bool], None]) -> None:
        """Register callback for partial/final transcripts.

        Args:
            callback(text: str, role: "other"|"user", is_final: bool)
        """
        self._on_transcript_cb = callback

    def on_utterance(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for completed utterances.

        Args:
            callback(text: str, role: "other"|"user")
        """
        self._on_utterance_cb = callback

    def start(self) -> None:
        """Open connection to STT service."""
        self._backend.set_callbacks(
            on_transcript=self._wrap_transcript,
            on_utterance=self._wrap_utterance,
        )
        self._backend.start()

    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk for transcription."""
        self._backend.send_audio(chunk)

    def stop(self) -> None:
        """Close connection."""
        self._backend.stop()

    @property
    def is_mock(self) -> bool:
        return isinstance(self._backend, MockTranscriberBackend)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _wrap_transcript(self, text: str, speaker: int, is_final: bool) -> None:
        if hasattr(self, "_on_transcript_cb") and self._on_transcript_cb:
            role = SPEAKER_MAP.get(speaker, "other")
            self._on_transcript_cb(text, role, is_final)

    def _wrap_utterance(self, text: str, speaker: int) -> None:
        if hasattr(self, "_on_utterance_cb") and self._on_utterance_cb:
            role = SPEAKER_MAP.get(speaker, "other")
            self._on_utterance_cb(text, role)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_transcriber(api_key: str = "") -> Transcriber:
    """Create a Transcriber, real or mock based on API key presence."""
    if api_key:
        backend = DeepgramBackend(api_key=api_key)
    else:
        backend = MockTranscriberBackend()
    return Transcriber(backend=backend)
