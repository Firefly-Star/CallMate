"""Tests for command handler."""
from callmate.core.command_handler import CommandHandler, Command


def handler(**kwargs):
    """Helper to create a CommandHandler with defaults."""
    return CommandHandler(**kwargs)


class TestCommandParsing:
    def test_parse_help(self):
        cmd = CommandHandler.parse("/help")
        assert cmd is not None
        assert cmd.name == "help"
        assert cmd.args == ""

    def test_parse_with_args(self):
        cmd = CommandHandler.parse("/profile 张老师")
        assert cmd is not None
        assert cmd.name == "profile"
        assert cmd.args == "张老师"

    def test_parse_not_a_command(self):
        assert CommandHandler.parse("普通文本") is None
        assert CommandHandler.parse("") is None

    def test_parse_case_insensitive(self):
        cmd = CommandHandler.parse("/Quit")
        assert cmd is not None
        assert cmd.name == "quit"

    def test_parse_trailing_spaces(self):
        cmd = CommandHandler.parse("  /help  ")
        assert cmd is not None
        assert cmd.name == "help"


class TestCommandHelp:
    def test_help_contains_commands(self):
        h = handler()
        result = h._cmd_help(Command("help"))
        assert "/help" in result
        assert "/quit" in result
        assert "/profile" in result
        assert "/refresh" in result
        assert "/note" in result

    def test_unknown_command(self):
        h = handler()
        result = h.execute(Command("unknown"))
        assert "未知命令" in result
        assert "/help" in result


class TestCommandQuit:
    def test_quit_calls_callback(self):
        called = False
        def on_quit():
            nonlocal called
            called = True
        h = handler(on_quit=on_quit)
        h._cmd_quit(Command("quit"))
        assert called is True


class TestCommandProfile:
    def test_show_current_profile(self):
        h = handler(get_current_profile=lambda: "张老师")
        result = h._cmd_profile(Command("profile"))
        assert "张老师" in result

    def test_switch_profile(self):
        switched = []
        def on_switch(name):
            switched.append(name)
            return f"已切换到: {name}"
        h = handler(on_profile_switch=on_switch)
        result = h._cmd_profile(Command("profile", "李四"))
        assert switched == ["李四"]
        assert "李四" in result

    def test_no_profile_selected_with_list(self):
        h = handler(get_profile_list=lambda: ["张老师", "李四"])
        result = h._cmd_profile(Command("profile"))
        assert "张老师" in result
        assert "李四" in result

    def test_no_profiles_at_all(self):
        h = handler()
        result = h._cmd_profile(Command("profile"))
        assert "没有预设对象" in result


class TestCommandRefresh:
    def test_refresh_calls_callback(self):
        called = False
        def on_refresh():
            nonlocal called
            called = True
        h = handler(on_refresh=on_refresh)
        h._cmd_refresh(Command("refresh"))
        assert called is True


class TestCommandNote:
    def test_note_calls_callback(self):
        notes = []
        def on_note(text):
            notes.append(text)
        h = handler(on_note=on_note)
        result = h._cmd_note(Command("note", "remember this"))
        assert notes == ["remember this"]
        assert "remember this" in result

    def test_note_empty_args(self):
        h = handler()
        result = h._cmd_note(Command("note"))
        assert "用法" in result
