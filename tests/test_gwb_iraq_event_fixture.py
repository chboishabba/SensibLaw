from __future__ import annotations

import json
from pathlib import Path


def test_gwb_iraq_event_fixture_structure() -> None:
    path = Path(__file__).resolve().parent / "fixtures" / "gwb_iraq_event_fixture.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    event = payload.get("event")
    assert event
    assert event["id"] == "gwb-iraq-invasion-2003"
    assert len(event.get("authority_nodes", [])) == 3
    titles = {node["title"] for node in event["authority_nodes"]}
    assert "UN Charter Article 2(4)" in titles
    assert "UN Charter Article 51" in titles
    assert "UN Charter Chapter VII" in titles
