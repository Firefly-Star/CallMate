"""Terminal UI presenter.

A lightweight terminal UI for CallMate with:
  - Scrolling conversation history
  - Suggestions panel
  - Input bar with slash commands
  - Real-time refresh using ANSI escape codes

Usage:
    ui = Presenter()
    ui.add_message("other", "你好")
    ui.update_suggestions([{"text": "回复", "reason": "理由"}])
    user_input = ui.get_input()
"""

from __future__ import annotations

import shutil
import sys
from typing import Optional


def _clear_screen() -> None:
    """Clear the terminal screen."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _hide_cursor() -> None:
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def _show_cursor() -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def _move_to(row: int, col: int = 0) -> None:
    sys.stdout.write(f"\033[{row};{col}H")


def _set_scroll_region(top: int, bottom: int) -> None:
    sys.stdout.write(f"\033[{top};{bottom}r")


def _reset_scroll_region() -> None:
    sys.stdout.write("\033[r")


# ---------------------------------------------------------------------------
# Presenter
# ---------------------------------------------------------------------------

class Presenter:
    """Terminal UI for CallMate."""

    HEADER_HEIGHT = 1   # title bar
    STATUS_HEIGHT = 1   # status message line
    INPUT_HEIGHT = 2    # input prompt + input line
    SUGGESTIONS_MAX = 6  # max lines for suggestions panel

    def __init__(self, profile_name: str = ""):
        self._profile_name = profile_name
        self._history: list[tuple[str, str]] = []  # (role, content)
        self._suggestions: list[dict] = []
        self._input_prompt = "> "
        self._status_message = ""
        self._streaming: Optional[tuple[str, str]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialize the UI: clear screen, draw static elements."""
        _clear_screen()
        _hide_cursor()
        self._draw_header()
        self._draw_input_area()
        self._refresh()
        _show_cursor()

    def stop(self) -> None:
        """Clean up the UI."""
        _show_cursor()
        _reset_scroll_region()
        print("\n")  # leave clean line after exit

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        label_map = {"user": "你", "other": "对方", "system": "系统"}
        label = label_map.get(role, role)
        self._history.append((label, content))
        self._refresh()

    def update_suggestions(self, suggestions: list[dict]) -> None:
        """Update the displayed suggestions."""
        self._suggestions = suggestions
        self._refresh()

    def set_status(self, message: str) -> None:
        """Set a status message displayed in the header area."""
        self._status_message = message
        self._refresh()

    def show_streaming(self, text: str, speaker: int) -> None:
        """Show streaming (interim) transcript.
        
        This updates a temporary line in the history area that gets
        overwritten as new interim results arrive. When the utterance
        is complete, use add_message() instead.
        """
        label_map = {0: "对方", 1: "你"}
        label = label_map.get(speaker, "对方")
        self._streaming = (label, text)
        self._refresh()

    def clear_streaming(self) -> None:
        """Remove the streaming line after utterance is finalized."""
        self._streaming = None
        self._refresh()

    def get_input(self) -> str:
        """Read a line of input from the user.

        Returns:
            The entered text (without trailing newline).
            Returns empty string on EOF/Ctrl-D.
        """
        try:
            _show_cursor()
            _move_to(self._input_row(), 0)
            sys.stdout.write(f"\033[K{self._input_prompt}")
            sys.stdout.flush()
            text = sys.stdin.readline()
            _hide_cursor()
            if not text:
                return ""
            return text.rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            return ""

    def clear_history(self) -> None:
        """Clear all displayed history."""
        self._history.clear()
        self._refresh()

    # ------------------------------------------------------------------
    # Layout calculations
    # ------------------------------------------------------------------

    @property
    def _rows(self) -> int:
        return shutil.get_terminal_size().lines

    @property
    def _cols(self) -> int:
        return shutil.get_terminal_size().columns

    def _history_area_height(self) -> int:
        """Number of rows available for conversation history."""
        return self._rows - self.HEADER_HEIGHT - self.STATUS_HEIGHT - self.INPUT_HEIGHT - self.SUGGESTIONS_MAX

    def _history_start_row(self) -> int:
        return self.HEADER_HEIGHT + 1

    def _suggestions_start_row(self) -> int:
        return self._history_start_row() + self._history_area_height() + self.STATUS_HEIGHT

    def _input_row(self) -> int:
        return self._rows - 1

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_header(self) -> None:
        title = f" CallMate — {'📞 ' + self._profile_name if self._profile_name else '🔇 未选择对象'}"
        _move_to(1, 0)
        sys.stdout.write(f"\033[44;97m{' ' * self._cols}\033[0m")  # blue bar
        _move_to(1, 0)
        sys.stdout.write(f"\033[44;97m{title}\033[0m")

    def _draw_input_area(self) -> None:
        row = self._input_row()
        # Clear input line
        _move_to(row, 0)
        sys.stdout.write(f"\033[K{self._input_prompt}")
        sys.stdout.flush()

    def _refresh(self) -> None:
        """Redraw the variable content areas (history + suggestions)."""
        self._draw_header()
        self._draw_status()
        self._draw_history()
        self._draw_suggestions()

    def _draw_status(self) -> None:
        """Draw the status message line."""
        row = self.HEADER_HEIGHT + 1 + self._history_area_height()
        _move_to(row, 0)
        msg = self._status_message[:self._cols - 1] if self._status_message else ""
        sys.stdout.write(f"\033[K\033[90m{msg}\033[0m")

    def _draw_history(self) -> None:
        """Draw conversation history in the scrolling region."""
        start_row = self._history_start_row()
        height = self._history_area_height()

        # Determine which portion of history to show (scroll to bottom)
        total_lines = []
        for label, content in self._history:
            if label:
                line = f" {label}: {content}"
            else:
                line = f" {content}"
            wrapped = self._wrap_text(line, self._cols)
            total_lines.extend(wrapped)

        # Add streaming line (if any)
        if self._streaming:
            label, text = self._streaming
            line = f" {label}: {text}"
            wrapped = self._wrap_text(line, self._cols)
            # Mark as streaming with dim text
            for i, wl in enumerate(wrapped):
                if i == 0:
                    total_lines.append(f"\033[2m{wl}\033[0m")  # dim
                else:
                    total_lines.append(f"\033[2m{wl}\033[0m")

        # Show only the last `height` lines
        visible = total_lines[-height:] if len(total_lines) > height else total_lines
        # Pad if needed
        visible = [""] * (height - len(visible)) + visible

        for i, line in enumerate(visible):
            row = start_row + i
            _move_to(row, 0)
            sys.stdout.write(f"\033[K{line[:self._cols]}")

    def _draw_suggestions(self) -> None:
        """Draw the suggestions panel."""
        start_row = self._suggestions_start_row()
        height = self.SUGGESTIONS_MAX

        lines = []
        if not self._suggestions:
            lines.append(" 等待对方的发言…")
        else:
            lines.append(" ─── 建议 ───")
            for i, s in enumerate(self._suggestions, 1):
                text = s.get("text", "")
                reason = s.get("reason", "")
                wrapped_text = self._wrap_text(f" {i}. {text}", self._cols)
                lines.extend(wrapped_text)
                if i < len(self._suggestions):
                    lines.append("")  # spacing between options
                if reason:
                    wrapped_reason = self._wrap_text(f"    └ {reason}", self._cols)
                    lines.extend(wrapped_reason)

        # Pad
        visible = lines[:height]
        visible = visible + [""] * (height - len(visible))

        for i, line in enumerate(visible):
            row = start_row + i
            sys.stdout.flush()
            sys.stdout.write(f"\033[{row};0H\033[K{line[:self._cols]}")

        sys.stdout.flush()

    @staticmethod
    def _wrap_text(text: str, max_width: int) -> list[str]:
        """Simple word-wrap that respects max_width."""
        if len(text) <= max_width:
            return [text]
        lines = []
        while text:
            if len(text) <= max_width:
                lines.append(text)
                break
            # Try to break at a space
            break_at = text.rfind(" ", 0, max_width)
            if break_at <= 0:
                break_at = max_width - 1
            lines.append(text[:break_at])
            text = text[break_at:].lstrip()
        return lines
