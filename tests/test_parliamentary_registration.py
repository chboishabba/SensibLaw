from __future__ import annotations

import json
from pathlib import Path


def test_parliamentary_sources_registered_in_foundation_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "foundation_sources.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = [source for source in (payload.get("sources") or []) if isinstance(source, dict)]
    names = {str(source.get("name") or "") for source in sources}
    expected = {
        "UK House of Commons Hansard",
        "UK House of Lords Hansard",
        "UK Select Committee Reports",
    }
    assert expected <= names
    for source in sources:
        if source.get("name") in expected:
            focus = source.get("focus_countries") or []
            assert "Iraq" in focus
