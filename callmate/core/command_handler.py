"""Slash command handler for CallMate.

Parses and executes `/` commands entered by the user.

Usage:
    handler = CommandHandler(presenter, dialogue_mgr, profile_store)
    cmd = handler.parse("/help")
    if cmd:
        handler.execute(cmd)
"""

from __future__ import annotations

from typing import Optional, Callable


# ---------------------------------------------------------------------------
# Command definition
# ---------------------------------------------------------------------------

class Command:
    """A parsed slash command."""

    def __init__(self, name: str, args: str = ""):
        self.name = name
        self.args = args


class CommandHandler:
    """Parses and executes slash commands."""

    def __init__(
        self,
        *,
        on_quit: Optional[Callable] = None,
        on_refresh: Optional[Callable] = None,
        on_profile_switch: Optional[Callable[[str], str]] = None,
        on_note: Optional[Callable[[str], None]] = None,
        get_profile_list: Optional[Callable[[], list[str]]] = None,
        get_current_profile: Optional[Callable[[], str]] = None,
    ):
        self._on_quit = on_quit
        self._on_refresh = on_refresh
        self._on_profile_switch = on_profile_switch
        self._on_note = on_note
        self._get_profile_list = get_profile_list or (lambda: [])
        self._get_current_profile = get_current_profile or (lambda: "")

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse(text: str) -> Optional[Command]:
        """Parse a slash command from user input.

        Returns None if the input is not a command.
        """
        text = text.strip()
        if not text.startswith("/"):
            return None
        parts = text[1:].split(maxsplit=1)
        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        return Command(name, args)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, cmd: Command) -> str:
        """Execute a parsed command and return a response message.

        The response message should be displayed to the user.
        """
        handler_name = f"_cmd_{cmd.name}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            return f"未知命令: /{cmd.name}。输入 /help 查看可用命令。"
        return handler(cmd)

    # ------------------------------------------------------------------
    # Built-in commands
    # ------------------------------------------------------------------

    def _cmd_help(self, cmd: Command) -> str:
        lines = [
            "可用命令:",
            "  /help             — 显示此帮助",
            "  /quit             — 结束通话，退出 CallMate",
            "  /profile          — 查看当前通话对象信息",
            "  /profile <名字>   — 切换到指定对象",
            "  /refresh          — 手动刷新建议",
            "  /note <文本>      — 添加备注（不会发给对方）",
        ]
        return "\n".join(lines)

    def _cmd_quit(self, cmd: Command) -> str:
        if self._on_quit:
            self._on_quit()
        return "通话已结束。"

    def _cmd_refresh(self, cmd: Command) -> str:
        if self._on_refresh:
            self._on_refresh()
        return "正在刷新建议…"

    def _cmd_profile(self, cmd: Command) -> str:
        if cmd.args:
            # Switch profile
            name = cmd.args.strip()
            if self._on_profile_switch:
                result = self._on_profile_switch(name)
                return result
            return f"已切换到: {name}"
        else:
            # Show current profile
            current = self._get_current_profile()
            if current:
                return f"当前通话对象: {current}"
            profiles = self._get_profile_list()
            if profiles:
                msg = "没有选择对象。可选对象:\n" + "\n".join(f"  /profile {p}" for p in profiles)
                return msg
            return "没有预设对象。通话中会尝试自动识别。"

    def _cmd_note(self, cmd: Command) -> str:
        if not cmd.args:
            return "用法: /note <文本>"
        if self._on_note:
            self._on_note(cmd.args)
        return f"备注已添加: {cmd.args}"
