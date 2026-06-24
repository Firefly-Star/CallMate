"""Dialogue history management + SOUL.md + prompt assembly.

Manages the conversation transcript and assembles the three-layer
prompt structure for the LLM advisor.

Usage:
    dm = DialogueManager()
    dm.add_message("other", "这周实验进展怎么样？")
    dm.add_message("user", "跑通了")
    soul_text, profile_text, transcript = dm.build_prompt(profile)
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from storage.profile_store import Profile


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Message:
    role: str  # "other" | "user"
    content: str
    time: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "time": self.time}


# ---------------------------------------------------------------------------
# Default SOUL.md content — created when no soul file exists
# ---------------------------------------------------------------------------

_DEFAULT_SOUL = """# SOUL.md — My Communication Style

This file describes how I talk. The AI assistant should use this to
make its suggestions sound like *me*, not like a generic bot.

## My Style
- I tend to speak casually, not overly formal.
- I prefer getting straight to the point before adding details.
- I use short sentences when I'm unsure or nervous.

## Things I Often Say
- "嗯…" (when thinking)
- "其实" (when I'm about to explain something)
- "好的" (to acknowledge)

## Notes
- When I'm on the phone with my advisor, I want to sound prepared and respectful.
- When talking to close friends, I can be much more relaxed.
- If I'm stuck on what to say, I prefer a simple starting point that I can build on.
"""


# ---------------------------------------------------------------------------
# Dialogue Manager
# ---------------------------------------------------------------------------

class DialogueManager:
    """Manages conversation history, SOUL.md, and prompt assembly."""

    def __init__(self, soul_path: Optional[str] = None):
        self._messages: list[Message] = []
        self._soul_path = soul_path or str(Path.home() / ".callmate" / "soul.md")
        self._ensure_soul()

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> Message:
        """Add a message to the history."""
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        return msg

    def get_history(self) -> list[dict]:
        """Return all messages as dicts."""
        return [m.to_dict() for m in self._messages]

    def clear(self) -> None:
        """Reset conversation history for a new session."""
        self._messages.clear()

    # ------------------------------------------------------------------
    # SOUL.md management
    # ------------------------------------------------------------------

    def load_soul(self) -> str:
        """Read SOUL.md content. Creates default if missing."""
        self._ensure_soul()
        return Path(self._soul_path).read_text(encoding="utf-8")

    def save_soul(self, content: str) -> None:
        """Write SOUL.md content."""
        Path(self._soul_path).write_text(content, encoding="utf-8")

    def _ensure_soul(self) -> None:
        path = Path(self._soul_path)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_DEFAULT_SOUL, encoding="utf-8")

    # ------------------------------------------------------------------
    # Prompt assembly (three-layer)
    # ------------------------------------------------------------------

    def build_prompt(self, profile: Optional[Profile] = None) -> tuple[str, str, list[dict]]:
        """Assemble the three-layer prompt.

        Returns:
            (soul_text, profile_text, transcript_messages)
        """
        soul_text = self.load_soul()

        if profile:
            profile_text = self._format_profile(profile)
        else:
            profile_text = ""

        transcript = self.get_history()
        return soul_text, profile_text, transcript

    @staticmethod
    def _format_profile(profile: Profile) -> str:
        """Format a Profile into a readable text block."""
        lines = [f"Name: {profile.name}"]
        if profile.relationship:
            lines.append(f"Relationship: {profile.relationship}")
        if profile.occasion:
            lines.append(f"Occasion: {profile.occasion}")
        if profile.topics:
            lines.append(f"Topics: {', '.join(profile.topics)}")
        if profile.notes:
            lines.append("Notes:")
            for note in profile.notes:
                lines.append(f"  - {note}")
        if profile.keywords:
            lines.append(f"Keywords: {', '.join(profile.keywords)}")
        return "\n".join(lines)
