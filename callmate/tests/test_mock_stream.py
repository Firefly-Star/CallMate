"""Tests for mock stream."""
from callmate.utils.mock_stream import MockStreamer, ConversationScript, Utterance


class TestMockStreamer:
    def test_empty_script(self):
        script = ConversationScript([])
        streamer = MockStreamer(script)
        events = []
        streamer.on_speech_started(lambda s: events.append(("start", s)))
        streamer.on_results(lambda t, s, f, sf: events.append(("result", t, s, f, sf)))
        streamer.on_utterance_end(lambda t, s: events.append(("end", t, s)))
        streamer.run()
        assert events == []

    def test_single_utterance(self):
        script = ConversationScript([
            Utterance(speaker=0, text="你好", duration_s=0.5, pause_after_s=0),
        ])
        streamer = MockStreamer(script)
        results = []
        streamer.on_results(lambda t, s, f, sf: results.append((t, s, f, sf)))
        streamer.run()
        assert len(results) >= 2  # at least final + speech_final
        assert results[-1] == ("你好", 0, True, True)  # last = speech_final

    def test_speaker_alternation(self):
        script = ConversationScript([
            Utterance(speaker=0, text="你好", duration_s=0.5, pause_after_s=0),
            Utterance(speaker=1, text="嗨", duration_s=0.5, pause_after_s=0),
        ])
        streamer = MockStreamer(script)
        speakers = []
        streamer.on_speech_started(lambda s: speakers.append(s))
        streamer.run()
        assert speakers == [0, 1]

    def test_utterance_end_called(self):
        script = ConversationScript([
            Utterance(speaker=0, text="测试", duration_s=0.5, pause_after_s=0),
        ])
        streamer = MockStreamer(script)
        ends = []
        streamer.on_utterance_end(lambda t, s: ends.append((t, s)))
        streamer.run()
        assert ends == [("测试", 0)]
