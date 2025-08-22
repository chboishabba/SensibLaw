from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "sensiblaw" / "schemas"


def load_schema(name: str) -> Dict[str, Any]:
    """Load a JSON schema by filename."""
    path = SCHEMA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate(data: Any, schema: Dict[str, Any]) -> None:
    """Validate ``data`` against a very small subset of JSON schema.

    This helper supports the parts of the specification used by the local
    schemas and avoids external dependencies.
    """
    typ = schema.get("type")
    if typ == "object":
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        for key in schema.get("required", []):
            if key not in data:
                raise ValueError(f"Missing required field '{key}'")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in data:
                validate(data[key], subschema)
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            for key, value in data.items():
                if key not in properties:
                    validate(value, additional)
    elif typ == "array":
        if not isinstance(data, list):
            raise ValueError("Expected array")
        item_schema = schema.get("items", {})
        for item in data:
            validate(item, item_schema)
    else:
        if typ == "string" and not isinstance(data, str):
            raise ValueError("Expected string")
        if typ == "boolean" and not isinstance(data, bool):
            raise ValueError("Expected boolean")
        if typ == "number" and not isinstance(data, (int, float)):
            raise ValueError("Expected number")


__all__ = ["load_schema", "validate"]
