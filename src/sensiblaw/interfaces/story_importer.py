from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Dict, Any, Sequence
import json


class StoryImporter(ABC):
    """Abstract interface for importing narrative events into storage."""

    @abstractmethod
    def import_stories(self, stories: Iterable[Dict[str, Any]]) -> None:
        """Import an iterable of story events into storage."""

    def import_from_file(self, filepath: str | Path) -> None:
        """Load events from ``filepath`` and import them.

        The file is expected to contain JSON data representing either a list of
        events or a mapping with an ``events`` key.
        """
        path = Path(filepath)
        with path.open("r", encoding="utf-8") as f:
            data: Any = json.load(f)
        if isinstance(data, dict):
            stories = data.get("events") or [data]
        else:
            stories = data
        self.import_stories(stories)  # type: ignore[arg-type]


__all__ = ["StoryImporter"]
