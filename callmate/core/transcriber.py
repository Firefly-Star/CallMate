"""Speech-to-text via Deepgram Listen V2 API.

Uses the Deepgram SDK v7's `listen.v2.connect()` for real-time
conversational speech recognition with built-in turn detection.

The V2 API provides turn events that map directly to our design:
  - Update      → interim transcript (ongoing)
  - StartOfTurn → someone started speaking
  - EagerEndOfTurn → speculative execution trigger
  - EndOfTurn   → final transcript, trigger LLM advice
  - TurnResumed → false alarm, cancel pending advice

Usage:
    transcriber = Transcriber(api_key="...")
    transcriber.on_transcript(lambda text, role, is_final: ...)
    transcriber.on_utterance(lambda text, role: ...)
    transcriber.start()
    transcriber.send_audio(chunk)
    transcriber.stop()
"""

from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from typing import Callable, Optional

from deepgram import DeepgramClient
from deepgram.core.events import EventType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
ENCODING = "linear16"
MODEL = "flux-general-en"
EAGER_EOT_THRESHOLD = 0.5
EOT_THRESHOLD = 0.8


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class TranscriberBackend(ABC):
    """Abstract STT backend."""

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def send_audio(self, chunk: bytes) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...


# ---------------------------------------------------------------------------
# Deepgram Listen V2 backend
# ---------------------------------------------------------------------------

class DeepgramV2Backend(TranscriberBackend):
    """Backend using Deepgram SDK Listen V2."""

    def __init__(
        self,
        api_key: str,
        model: str = MODEL,
        sample_rate: int = SAMPLE_RATE,
        encoding: str = ENCODING,
    ):
        self._api_key = api_key
        self._model = model
        self._sample_rate = sample_rate
        self._encoding = encoding
        self._client: Optional[DeepgramClient] = None
        self._connection = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Callbacks
        self._on_transcript: Optional[Callable] = None
        self._on_utterance: Optional[Callable] = None
        self._on_eager_eot: Optional[Callable] = None

    def set_callbacks(
        self,
        on_transcript: Optional[Callable[[str, int, bool], None]] = None,
        on_utterance: Optional[Callable[[str, int], None]] = None,
        on_eager_eot: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self._on_transcript = on_transcript
        self._on_utterance = on_utterance
        self._on_eager_eot = on_eager_eot

    def start(self) -> None:
        self._client = DeepgramClient(api_key=self._api_key)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def send_audio(self, chunk: bytes) -> None:
        if self._connection:
            try:
                self._connection.send_media(chunk)
            except Exception:
                pass

    def stop(self) -> None:
        self._running = False
        if self._connection:
            try:
                self._connection.send_close_stream()
            except Exception:
                pass
            self._connection = None

    def is_connected(self) -> bool:
        return self._connection is not None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Background thread: open connection and listen for messages."""
        try:
            with self._client.listen.v2.connect(
                model=self._model,
                encoding=self._encoding,
                sample_rate=self._sample_rate,
                eager_eot_threshold=EAGER_EOT_THRESHOLD,
                eot_threshold=EOT_THRESHOLD,
            ) as connection:
                self._connection = connection

                connection.on(EventType.OPEN, lambda _: None)
                connection.on(EventType.CLOSE, lambda _: self._stop_self())
                connection.on(EventType.ERROR, lambda err: None)

                # Process messages inline
                connection.start_listening()
                for msg in connection:
                    if not self._running:
                        break
                    self._handle_message(msg)

        except Exception:
            pass
        finally:
            self._connection = None

    def _stop_self(self) -> None:
        self._running = False

    def _handle_message(self, msg) -> None:
        """Handle a parsed V2 message."""
        msg_type = getattr(msg, "type", "")

        if msg_type != "TurnInfo":
            return

        event = getattr(msg, "event", None)
        if event is None:
            return

        event_name = getattr(event, "value", "") if hasattr(event, "value") else str(event)
        transcript = getattr(msg, "transcript", "")
        turn_index = getattr(msg, "turn_index", 0)

        # Infer speaker from turn parity (0,2,4 → other; 1,3,5 → user)
        speaker = 0 if turn_index % 2 == 0 else 1

        if event_name == "Update" and transcript:
            # Interim transcript update
            if self._on_transcript:
                self._on_transcript(transcript, speaker, is_final=False)

        elif event_name == "EagerEndOfTurn" and transcript:
            # Speculative: user might be done
            if self._on_eager_eot:
                self._on_eager_eot(transcript, speaker)

        elif event_name == "EndOfTurn" and transcript:
            # Final transcript for this turn
            if self._on_transcript:
                self._on_transcript(transcript, speaker, is_final=True)
            if self._on_utterance:
                self._on_utterance(transcript, speaker)


# ---------------------------------------------------------------------------
# Mock backend (for testing without API key)
# ---------------------------------------------------------------------------

class MockTranscriberBackend(TranscriberBackend):
    """Mock backend for testing. Inject transcripts/utterances manually."""

    def __init__(self):
        self._connected = False
        self._on_transcript: Optional[Callable] = None
        self._on_utterance: Optional[Callable] = None
        self._on_eager_eot: Optional[Callable] = None
        self._received_chunks: list[bytes] = []

    def set_callbacks(
        self,
        on_transcript: Optional[Callable[[str, int, bool], None]] = None,
        on_utterance: Optional[Callable[[str, int], None]] = None,
        on_eager_eot: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self._on_transcript = on_transcript
        self._on_utterance = on_utterance
        self._on_eager_eot = on_eager_eot

    def start(self) -> None:
        self._connected = True

    def send_audio(self, chunk: bytes) -> None:
        self._received_chunks.append(chunk)

    def stop(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def inject_transcript(self, text: str, speaker: int = 0, is_final: bool = True) -> None:
        if self._on_transcript:
            self._on_transcript(text, speaker, is_final)

    def inject_utterance(self, text: str, speaker: int = 0) -> None:
        if self._on_utterance:
            self._on_utterance(text, speaker)

    def inject_eager_eot(self, text: str, speaker: int = 0) -> None:
        if self._on_eager_eot:
            self._on_eager_eot(text, speaker)


# ---------------------------------------------------------------------------
# High-level Transcriber
# ---------------------------------------------------------------------------

SPEAKER_MAP = {0: "other", 1: "user"}


class Transcriber:
    """High-level STT manager.

    Wraps Deepgram V2 (real) or Mock backend with consistent callbacks.
    """

    def __init__(self, backend: Optional[TranscriberBackend] = None):
        self._backend = backend or MockTranscriberBackend()
        self._on_transcript_cb: Optional[Callable] = None
        self._on_utterance_cb: Optional[Callable] = None
        self._on_eager_eot_cb: Optional[Callable] = None

    def on_transcript(self, callback: Callable[[str, str, bool], None]) -> None:
        """Interim or final transcript. (text, role, is_final)"""
        self._on_transcript_cb = callback

    def on_utterance(self, callback: Callable[[str, str], None]) -> None:
        """Completed utterance. (text, role)"""
        self._on_utterance_cb = callback

    def on_eager_eot(self, callback: Callable[[str, str], None]) -> None:
        """Speculative end-of-turn signal. (text, role)"""
        self._on_eager_eot_cb = callback

    def start(self) -> None:
        self._backend.set_callbacks(
            on_transcript=self._wrap_transcript,
            on_utterance=self._wrap_utterance,
            on_eager_eot=self._wrap_eager_eot,
        )
        self._backend.start()

    def send_audio(self, chunk: bytes) -> None:
        self._backend.send_audio(chunk)

    def stop(self) -> None:
        self._backend.stop()

    @property
    def is_mock(self) -> bool:
        return isinstance(self._backend, MockTranscriberBackend)

    # ------------------------------------------------------------------
    # Internal wrappers
    # ------------------------------------------------------------------

    def _wrap_transcript(self, text: str, speaker: int, is_final: bool) -> None:
        if self._on_transcript_cb:
            role = SPEAKER_MAP.get(speaker, "other")
            self._on_transcript_cb(text, role, is_final)

    def _wrap_utterance(self, text: str, speaker: int) -> None:
        if self._on_utterance_cb:
            role = SPEAKER_MAP.get(speaker, "other")
            self._on_utterance_cb(text, role)

    def _wrap_eager_eot(self, text: str, speaker: int) -> None:
        if self._on_eager_eot_cb:
            role = SPEAKER_MAP.get(speaker, "other")
            self._on_eager_eot_cb(text, role)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_transcriber(api_key: str = "") -> Transcriber:
    if api_key:
        backend = DeepgramV2Backend(api_key=api_key)
    else:
        backend = MockTranscriberBackend()
    return Transcriber(backend=backend)
