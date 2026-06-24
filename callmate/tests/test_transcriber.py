"""Tests for transcriber."""
import pytest
from callmate.core.transcriber import (
    Transcriber,
    MockTranscriberBackend,
    DeepgramBackend,
    create_transcriber,
    SPEAKER_MAP,
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
        backend = MockTranscriberBackend()
        backend.start()
        assert backend.is_connected() is True
        backend.stop()
        assert backend.is_connected() is False

    def test_send_audio(self):
        backend = MockTranscriberBackend()
        backend.start()
        backend.send_audio(b"\x00\x01\x02")
        assert len(backend._received_chunks) == 1
        backend.stop()

    def test_inject_transcript(self):
        backend = MockTranscriberBackend()
        results = []
        backend.set_callbacks(
            on_transcript=lambda t, s, f: results.append((t, s, f)),
        )
        backend.inject_transcript("你好", 0, True)
        assert results == [("你好", 0, True)]

    def test_inject_utterance(self):
        backend = MockTranscriberBackend()
        results = []
        backend.set_callbacks(on_utterance=lambda t, s: results.append((t, s)))
        backend.inject_utterance("实验进展如何", 1)
        assert results == [("实验进展如何", 1)]

    def test_multiple_callbacks(self):
        backend = MockTranscriberBackend()
        transcripts = []
        utterances = []
        backend.set_callbacks(
            on_transcript=lambda t, s, f: transcripts.append((t, s, f)),
            on_utterance=lambda t, s: utterances.append((t, s)),
        )
        backend.inject_transcript("你好", 0, False)
        backend.inject_utterance("你好", 0)
        assert len(transcripts) == 1
        assert len(utterances) == 1


class TestTranscriber:
    def test_mock_fallback(self):
        t = create_transcriber()  # no API key → mock
        assert t.is_mock is True

    def test_start_stop_mock(self):
        t = create_transcriber()
        t.on_transcript(lambda text, role, is_final: None)
        t.on_utterance(lambda text, role: None)
        t.start()
        t.stop()

    def test_send_audio_no_crash(self):
        t = create_transcriber()
        t.start()
        t.send_audio(b"\x00" * 3200)  # typical chunk size
        t.stop()

    def test_transcript_maps_speaker(self):
        backend = MockTranscriberBackend()
        t = Transcriber(backend=backend)
        results = []
        t.on_transcript(lambda text, role, is_final: results.append((text, role, is_final)))
        t.start()
        backend.inject_transcript("你好", 0, True)
        assert results == [("你好", "other", True)]

    def test_utterance_maps_speaker(self):
        backend = MockTranscriberBackend()
        t = Transcriber(backend=backend)
        results = []
        t.on_utterance(lambda text, role: results.append((text, role)))
        t.start()
        backend.inject_utterance("实验进展如何", 1)
        assert results == [("实验进展如何", "user")]

    def test_stop_before_start(self):
        t = create_transcriber()
        t.stop()  # should not crash

    def test_send_before_start(self):
        t = create_transcriber()
        t.send_audio(b"test")  # should not crash


class TestDeepgramBackend:
    def test_no_api_key(self):
        """Deepgram backend requires API key."""
        backend = DeepgramBackend(api_key="")
        # Should not crash but connection will fail
        assert backend.is_connected() is False

    def test_build_url_contains_params(self):
        backend = DeepgramBackend(api_key="test_key")
        url = backend._build_url()
        assert "api.deepgram.com" in url
        assert "diarize=true" in url
        assert "encoding=linear16" in url
        assert "sample_rate=16000" in url
        assert "model=nova-2" in url

    def test_build_url_with_auth(self):
        backend = DeepgramBackend(api_key="sk_test_123")
        url = backend._build_url()
        # Auth is via headers, not URL params
        assert "sk_test" not in url


class TestFactory:
    def test_create_with_key_uses_deepgram(self):
        t = create_transcriber(api_key="sk_test")
        assert t.is_mock is False

    def test_create_without_key_uses_mock(self):
        t = create_transcriber()
        assert t.is_mock is True
