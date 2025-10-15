from __future__ import annotations

from typing import Any, Dict, Iterable, List

from schema_utils import load_schema, validate

_EVENT_SCHEMA = load_schema("event.schema.yaml")
_RULE_CHECK_SCHEMA = load_schema("rule_check.schema.yaml")


class StoryImporter:
    """Import stories and validate their structure."""

    def import_events(self, events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and return a list of event dictionaries."""
        validated: List[Dict[str, Any]] = []
        for event in events:
            validate(event, _EVENT_SCHEMA)
            validated.append(event)
        return validated

    def export_checks(self, checks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and return rule check results."""
        validated: List[Dict[str, Any]] = []
        for check in checks:
            validate(check, _RULE_CHECK_SCHEMA)
            validated.append(check)
        return validated


__all__ = ["StoryImporter"]
