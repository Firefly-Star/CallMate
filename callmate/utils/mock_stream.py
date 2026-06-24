#!/usr/bin/env python3
"""Mock streaming transcriber — simulates Deepgram V1 real-time output.

Generates realistic events (SpeechStarted → Results → UtteranceEnd)
with proper timing and speaker alternation, matching Deepgram's actual
output format.

Usage:
    python mock_stream.py                     # Default demo conversation
    python mock_stream.py --script my_conv.json
"""

from __future__ import annotations

import json
import time
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Conversation script types
# ---------------------------------------------------------------------------

@dataclass
class Utterance:
    """A single utterance in a mock conversation."""

    speaker: int       # 0 = other, 1 = user
    text: str           # What they say
    duration_s: float   # How long they speak (seconds)
    pause_after_s: float = 1.0  # Pause before the next person speaks


@dataclass
class ConversationScript:
    """A complete mock conversation with timing."""

    utterances: list[Utterance] = field(default_factory=list)


def demo_conversation() -> ConversationScript:
    """Create a realistic demo conversation."""
    return ConversationScript([
        Utterance(speaker=0, text="这周实验进展怎么样？", duration_s=2.0, pause_after_s=1.5),
        Utterance(speaker=1, text="跑通了，效果不错", duration_s=1.5, pause_after_s=0.8),
        Utterance(speaker=0, text="那下周能写论文了吗", duration_s=1.8, pause_after_s=1.2),
        Utterance(speaker=1, text="嗯，下周可以开始写初稿", duration_s=2.0, pause_after_s=0.5),
        Utterance(speaker=0, text="好的，那下周一我们碰一下大纲", duration_s=2.2, pause_after_s=0),
    ])


# ---------------------------------------------------------------------------
# Mock Streamer
# ---------------------------------------------------------------------------

class MockStreamer:
    """Simulates Deepgram real-time events with realistic timing.

    Events generated:
      - SpeechStarted(speaker)
      - Results(transcript, is_final, speech_final, speaker) × N
      - UtteranceEnd(transcript, speaker)
    """

    def __init__(self, script: Optional[ConversationScript] = None):
        self._script = script or demo_conversation()
        self._on_speech_started: Optional[Callable] = None
        self._on_results: Optional[Callable] = None
        self._on_utterance_end: Optional[Callable] = None

    def on_speech_started(self, cb: Callable[[int], None]) -> None:
        self._on_speech_started = cb

    def on_results(self, cb: Callable[..., None]) -> None:
        """cb(transcript, speaker, is_final, speech_final)"""
        self._on_results = cb

    def on_utterance_end(self, cb: Callable[[str, int], None]) -> None:
        self._on_utterance_end = cb

    def run(self) -> None:
        """Run the mock conversation in real-time."""
        for utt in self._script.utterances:
            word_count = len(utt.text)
            words = list(utt.text)

            # SpeechStarted
            if self._on_speech_started:
                self._on_speech_started(utt.speaker)

            # Simulate incremental transcription (Update-style)
            # Send partial results at word intervals
            num_updates = max(1, word_count // 2)  # ~every 2 chars
            chars_per_update = max(1, word_count // num_updates)

            partial_text = ""
            for i in range(0, word_count, chars_per_update):
                chunk = utt.text[i:i + chars_per_update]
                partial_text += chunk
                is_final = (i + chars_per_update >= word_count)

                # Simulate timing between updates
                time.sleep(utt.duration_s / num_updates * 0.3)

                if self._on_results:
                    self._on_results(partial_text, utt.speaker, False, False)

            # Final result (is_final=True, speech_final=False)
            if self._on_results:
                self._on_results(utt.text, utt.speaker, True, False)

            # UtteranceEnd
            time.sleep(0.3)
            if self._on_utterance_end:
                self._on_utterance_end(utt.text, utt.speaker)

            # Final result with speech_final=True
            if self._on_results:
                self._on_results(utt.text, utt.speaker, True, True)

            # Pause before next utterance
            if utt.pause_after_s > 0:
                time.sleep(utt.pause_after_s)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", default=True)
    args = parser.parse_args()

    script = demo_conversation()
    streamer = MockStreamer(script)

    def on_start(speaker):
        role = "对方" if speaker == 0 else "你"
        print(f"[SpeechStarted] {role} 开始说话")

    def on_results(text, speaker, is_final, speech_final):
        role = "对方" if speaker == 0 else "你"
        label = "FINAL" if is_final else "interim"
        print(f"[{label:7s}] {role}: {text}")
        if speech_final:
            print(f"         └── speech_final=True ✓")

    def on_utterance_end(text, speaker):
        role = "对方" if speaker == 0 else "你"
        print(f"[UtteranceEnd] {role}: {text}")

    streamer.on_speech_started(on_start)
    streamer.on_results(on_results)
    streamer.on_utterance_end(on_utterance_end)

    print("=" * 50)
    print(" Mock Streaming Conversation")
    print("=" * 50)
    print()
    streamer.run()
    print()
    print("=" * 50)
    print(" Conversation ended")
    print("=" * 50)


if __name__ == "__main__":
    main()
