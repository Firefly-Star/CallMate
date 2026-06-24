"""Profile (contact info) CRUD via JSON.

Stores contact profiles at ~/.callmate/profiles.json.
Each profile describes who the user is talking to, their relationship,
and context notes for the LLM advisor.

Usage:
    store = ProfileStore()
    store.list()           # -> list of profile names
    store.get("张老师")    # -> Profile | None
    store.save(profile)    # create or update
    store.delete("张老师") # -> bool
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Profile:
    """Contact profile for a call recipient."""

    name: str
    relationship: str = ""
    occasion: str = ""
    topics: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            name=data.get("name", ""),
            relationship=data.get("relationship", ""),
            occasion=data.get("occasion", ""),
            topics=data.get("topics", []),
            notes=data.get("notes", []),
            keywords=data.get("keywords", []),
        )


_DEFAULT_PROFILES = [
    Profile(
        name="张老师",
        relationship="研究生导师",
        occasion="周报电话",
        topics=["上周实验进展", "下周计划", "论文投稿"],
        notes=[
            "张老师比较注重时间观念",
            "他喜欢学生先提出问题再给方案",
        ],
    ),
]


class ProfileStore:
    """Manages contact profiles stored as JSON."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = str(Path.home() / ".callmate" / "profiles.json")
        self._path = path
        self._ensure_file()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list(self) -> list[str]:
        """Return sorted list of profile names."""
        data = self._read()
        return sorted(p["name"] for p in data)

    def get(self, name: str) -> Optional[Profile]:
        """Return a profile by name, or None if not found."""
        data = self._read()
        for item in data:
            if item["name"] == name:
                return Profile.from_dict(item)
        return None

    def save(self, profile: Profile) -> None:
        """Create or update a profile."""
        data = self._read()
        replaced = False
        for i, item in enumerate(data):
            if item["name"] == profile.name:
                data[i] = asdict(profile)
                replaced = True
                break
        if not replaced:
            data.append(asdict(profile))
        self._write(data)

    def delete(self, name: str) -> bool:
        """Delete a profile by name. Returns True if deleted."""
        data = self._read()
        new_data = [item for item in data if item["name"] != name]
        if len(new_data) == len(data):
            return False
        self._write(new_data)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        path = Path(self._path)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write([asdict(p) for p in _DEFAULT_PROFILES])

    def _read(self) -> list[dict]:
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: list[dict]) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
