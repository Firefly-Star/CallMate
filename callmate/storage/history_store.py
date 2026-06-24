"""Call history save, load, and search.

Stores completed call records at ~/.callmate/history/ as individual JSON files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class HistoryStore:
    """Manages call history records."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = str(Path.home() / ".callmate" / "history")
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: dict) -> str:
        """Save a call record and return its filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"call_{timestamp}.json"
        path = self._dir / filename
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return filename

    def list(self) -> list[dict]:
        """Return all call records sorted by time (newest first)."""
        files = sorted(self._dir.glob("call_*.json"), reverse=True)
        records = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data.setdefault("filename", f.name)
                records.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return records

    def search(self, query: str) -> list[dict]:
        """Simple keyword search over call history."""
        query = query.lower()
        results = []
        for record in self.list():
            full_text = json.dumps(record, ensure_ascii=False).lower()
            if query in full_text:
                results.append(record)
        return results[:5]
