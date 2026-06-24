"""Tests for transcriber (Deepgram Listen V2)."""
import pytest
from callmate.core.transcriber import (
    Transcriber,
    MockTranscriberBackend,
    DeepgramV2Backend,
    create_transcriber,
    SPEAKER_MAP,
    MODEL,
    EAGER_EOT_THRESHOLD,
    EOT_THRESHOLD,
)


class TestSpeakerMap:
    def test_map_other(self):
        assert SPEAKER_MAP[0] == "other"

    def test_map_user(self):
        assert SPEAKER_MAP[1] == "user"

    def test_map_unknown(self):
        assert SPEAKER_MAP.get(99, "other") == "other"


class TestMockTranscriber:
    def test_start_stop(self):
        b = MockTranscriberBackend()
        b.start()
        assert b.is_connected() is True
        b.stop()
        assert b.is_connected() is False

    def test_send_audio(self):
        b = MockTranscriberBackend()
        b.start()
        b.send_audio(b"\x00\x01")
        assert len(b._received_chunks) == 1
        b.stop()

    def test_inject_transcript(self):
        b = MockTranscriberBackend()
        r = []
        b.set_callbacks(on_transcript=lambda t, s, f: r.append((t, s, f)))
        b.inject_transcript("你好", 0, True)
        assert r == [("你好", 0, True)]

    def test_inject_utterance(self):
        b = MockTranscriberBackend()
        r = []
        b.set_callbacks(on_utterance=lambda t, s: r.append((t, s)))
        b.inject_utterance("实验进展如何", 1)
        assert r == [("实验进展如何", 1)]

    def test_inject_eager_eot(self):
        b = MockTranscriberBackend()
        r = []
        b.set_callbacks(on_eager_eot=lambda t, s: r.append((t, s)))
        b.inject_eager_eot("好的", 0)
        assert r == [("好的", 0)]


class TestTranscriber:
    def test_mock_fallback(self):
        t = create_transcriber()
        assert t.is_mock is True

    def test_start_stop_mock(self):
        t = create_transcriber()
        t.on_transcript(lambda text, role, is_final: None)
        t.start()
        t.stop()

    def test_on_transcript_maps_speaker(self):
        b = MockTranscriberBackend()
        t = Transcriber(backend=b)
        r = []
        t.on_transcript(lambda text, role, is_final: r.append((text, role, is_final)))
        t.start()
        b.inject_transcript("你好", 0, True)
        assert r == [("你好", "other", True)]

    def test_on_utterance_maps_speaker(self):
        b = MockTranscriberBackend()
        t = Transcriber(backend=b)
        r = []
        t.on_utterance(lambda text, role: r.append((text, role)))
        t.start()
        b.inject_utterance("实验进展", 1)
        assert r == [("实验进展", "user")]

    def test_on_eager_eot_maps_speaker(self):
        b = MockTranscriberBackend()
        t = Transcriber(backend=b)
        r = []
        t.on_eager_eot(lambda text, role: r.append((text, role)))
        t.start()
        b.inject_eager_eot("好的", 0)
        assert r == [("好的", "other")]

    def test_stop_before_start(self):
        t = create_transcriber()
        t.stop()

    def test_send_audio_before_start(self):
        t = create_transcriber()
        t.send_audio(b"test")


class TestDeepgramBackend:
    def test_no_api_key(self):
        b = DeepgramV2Backend(api_key="")
        assert b.is_connected() is False

    def test_configured_values(self):
        b = DeepgramV2Backend(api_key="test", model=MODEL)
        assert b._model == "flux-general-en"
        assert b._sample_rate == 16000
        assert b._encoding == "linear16"

    def test_eager_threshold(self):
        assert EAGER_EOT_THRESHOLD == 0.5

    def test_eot_threshold(self):
        assert EOT_THRESHOLD == 0.8


class TestFactory:
    def test_create_with_key(self):
        t = create_transcriber(api_key="sk_test")
        assert t.is_mock is False

    def test_create_without_key(self):
        t = create_transcriber()
        assert t.is_mock is True
