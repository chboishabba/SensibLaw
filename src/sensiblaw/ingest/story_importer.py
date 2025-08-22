from __future__ import annotations

from pathlib import Path
from typing import Iterable, Dict, Any

import jsonschema
import yaml

from sensiblaw.interfaces.story_importer import StoryImporter
from storage.core import Storage


class DefaultStoryImporter(StoryImporter):
    """Validate and import story events into :class:`~storage.core.Storage`."""

    def __init__(self, storage: Storage, schema_path: str | Path | None = None) -> None:
        self.storage = storage
        if schema_path is None:
            schema_path = Path(__file__).resolve().parents[3] / "schemas" / "event.schema.yaml"
        with Path(schema_path).open("r", encoding="utf-8") as f:
            self.schema = yaml.safe_load(f)

    def import_stories(self, stories: Iterable[Dict[str, Any]]) -> None:
        for event in stories:
            jsonschema.validate(event, self.schema)
            event_type = event.get("type", "event")
            data = event.get("data", {})
            self.storage.insert_node(event_type, data)


__all__ = ["DefaultStoryImporter"]
