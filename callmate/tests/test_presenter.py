"""Tests for presenter.

Note: Full UI rendering tests require a real terminal. These tests
cover the logic layer: layout math, text wrapping, data management.
"""

from callmate.core.presenter import Presenter


class TestPresenterTextWrap:
    def test_short_text(self):
        result = Presenter._wrap_text("hello", 80)
        assert result == ["hello"]

    def test_exact_width(self):
        result = Presenter._wrap_text("a" * 80, 80)
        assert len(result) == 1

    def test_wraps_long_text(self):
        result = Presenter._wrap_text("hello world", 6)
        # Should wrap at word boundary
        assert len(result) >= 2
        assert result[0] == "hello"

    def test_wrap_no_spaces(self):
        result = Presenter._wrap_text("a" * 100, 20)
        assert len(result) >= 5
        for line in result:
            assert len(line) <= 20


class TestPresenterLayout:
    def test_history_area_height(self):
        p = Presenter()
        assert p._history_area_height() >= 5  # Minimum size with small terminal

    def test_history_start_row(self):
        p = Presenter()
        assert p._history_start_row() == 2  # HEADER_HEIGHT + 1

    def test_suggestions_start_row(self):
        p = Presenter()
        assert p._suggestions_start_row() > p._history_start_row()


class TestPresenterData:
    def test_add_message(self):
        p = Presenter()
        p.add_message("other", "你好")
        assert len(p._history) == 1
        assert p._history[0] == ("对方", "你好")

    def test_add_user_message(self):
        p = Presenter()
        p.add_message("user", "嗨")
        assert p._history[0] == ("你", "嗨")

    def test_update_suggestions(self):
        p = Presenter()
        suggestions = [{"text": "建议一", "reason": "理由"}]
        p.update_suggestions(suggestions)
        assert p._suggestions == suggestions

    def test_clear_history(self):
        p = Presenter()
        p.add_message("other", "你好")
        p.clear_history()
        assert p._history == []

    def test_multiple_messages(self):
        p = Presenter()
        p.add_message("other", "第一句")
        p.add_message("user", "第二句")
        p.add_message("other", "第三句")
        assert len(p._history) == 3

    def test_header_shows_profile(self):
        p = Presenter(profile_name="张老师")
        assert "张老师" in p._profile_name

    def test_header_no_profile(self):
        p = Presenter()
        assert p._profile_name == ""

    def test_status_message(self):
        p = Presenter()
        p.set_status("测试状态")
        assert "测试状态" in p._status_message

    def test_empty_suggestions(self):
        p = Presenter()
        assert p._suggestions == []
