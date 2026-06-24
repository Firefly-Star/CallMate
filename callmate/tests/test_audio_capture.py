"""Tests for audio_capture."""
import pytest
from callmate.core.audio_capture import (
    AudioCapture,
    AudioDevice,
    MockAudioBackend,
    PulseAudioBackend,
    CHUNK_SIZE,
)


class TestAudioDevice:
    def test_create_device(self):
        d = AudioDevice("test", "Test Mic")
        assert d.name == "test"
        assert d.description == "Test Mic"
        assert d.is_monitor is False

    def test_monitor_device(self):
        d = AudioDevice("monitor", "Monitor", is_monitor=True)
        assert d.is_monitor is True


class TestMockAudioBackend:
    def test_is_available(self):
        backend = MockAudioBackend()
        assert backend.is_available() is True

    def test_list_devices(self):
        backend = MockAudioBackend()
        devices = backend.list_devices()
        assert len(devices) >= 2
        assert any("Microphone" in d.description for d in devices)

    def test_start_stop(self):
        backend = MockAudioBackend()
        chunks = []
        backend.start_stream("default", lambda c: chunks.append(c))
        assert backend._running is True
        backend.stop_stream()
        assert backend._running is False

    def test_feed_chunk(self):
        backend = MockAudioBackend()
        chunks = []
        backend.start_stream("default", lambda c: chunks.append(c))
        backend.feed_chunk(b"test_audio_data")
        assert chunks == [b"test_audio_data"]
        backend.stop_stream()


class TestAudioCapture:
    def test_mock_fallback(self):
        capture = AudioCapture(backend=MockAudioBackend())
        assert capture.is_mock is True

    def test_list_devices_mock(self):
        capture = AudioCapture(backend=MockAudioBackend())
        devices = capture.list_devices()
        assert len(devices) > 0

    def test_start_needs_callback(self):
        capture = AudioCapture(backend=MockAudioBackend())
        with pytest.raises(RuntimeError, match="Set a callback"):
            capture.start()

    def test_on_chunk_and_start(self):
        capture = AudioCapture(backend=MockAudioBackend())
        chunks = []
        capture.on_chunk(lambda c: chunks.append(c))
        capture.start()
        # Feed some mock data through the backend
        capture._backend.feed_chunk(b"\x00" * CHUNK_SIZE)
        capture.stop()
        # chunk callback is stored
        assert capture._callback is not None

    def test_stop_without_start(self):
        capture = AudioCapture(backend=MockAudioBackend())
        capture.stop()  # should not crash

    def test_stop_twice(self):
        capture = AudioCapture(backend=MockAudioBackend())
        capture.on_chunk(lambda c: None)
        capture.start()
        capture.stop()
        capture.stop()  # should not crash


class TestPulseAudioBackend:
    def test_available_in_ci(self):
        """PulseAudio may not be available in CI, that's fine."""
        backend = PulseAudioBackend()
        # Should not crash regardless
        devices = backend.list_devices()
        assert isinstance(devices, list)
