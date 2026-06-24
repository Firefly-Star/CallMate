"""Tests for audio_capture."""
import pytest
from callmate.core.audio_capture import (
    AudioCapture,
    AudioDevice,
    MockAudioBackend,
    SoundDeviceBackend,
    BLOCK_SIZE,
)


class TestAudioDevice:
    def test_create_device(self):
        d = AudioDevice(0, "Test Mic", 1)
        assert d.device_id == 0
        assert d.name == "Test Mic"
        assert d.is_default is False

    def test_default_device(self):
        d = AudioDevice(1, "Default", 1, is_default=True)
        assert d.is_default is True


class TestMockAudioBackend:
    def test_is_available(self):
        b = MockAudioBackend()
        assert b.is_available() is True

    def test_list_devices(self):
        b = MockAudioBackend()
        devices = b.list_devices()
        assert len(devices) >= 2

    def test_start_stop(self):
        b = MockAudioBackend()
        chunks = []
        b.start_stream(0, lambda c: chunks.append(c))
        assert b._running is True
        b.stop_stream()
        assert b._running is False

    def test_feed_chunk(self):
        b = MockAudioBackend()
        chunks = []
        b.start_stream(0, lambda c: chunks.append(c))
        b.feed_chunk(b"test_data")
        assert chunks == [b"test_data"]
        b.stop_stream()


class TestAudioCapture:
    def test_mock_fallback(self):
        c = AudioCapture(backend=MockAudioBackend())
        assert c.is_mock is True

    def test_list_devices_mock(self):
        c = AudioCapture(backend=MockAudioBackend())
        devices = c.list_devices()
        assert len(devices) > 0

    def test_start_needs_callback(self):
        c = AudioCapture(backend=MockAudioBackend())
        with pytest.raises(RuntimeError, match="Set a callback"):
            c.start()

    def test_on_chunk_and_start(self):
        c = AudioCapture(backend=MockAudioBackend())
        c.on_chunk(lambda _: None)
        c.start()
        c.stop()

    def test_stop_without_start(self):
        c = AudioCapture(backend=MockAudioBackend())
        c.stop()

    def test_stop_twice(self):
        c = AudioCapture(backend=MockAudioBackend())
        c.on_chunk(lambda _: None)
        c.start()
        c.stop()
        c.stop()


class TestSoundDeviceBackend:
    def test_list_devices_safe(self):
        """Should not crash even with 0 devices."""
        b = SoundDeviceBackend()
        devices = b.list_devices()
        assert isinstance(devices, list)
