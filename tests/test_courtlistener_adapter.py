from __future__ import annotations

import json

from src.ontology.courtlistener import build_courtlistener_statute_case_follow
from src.sources.courtlistener import CourtListenerStatuteAdapter


def test_courtlistener_adapter_fetch_returns_known_statute() -> None:
    adapter = CourtListenerStatuteAdapter()
    result = adapter.fetch("statute:us:section:1983")
    payload = json.loads(result.content.decode("utf-8"))
    assert payload["statute_id"] == "statute:us:section:1983"
    assert payload["title"].startswith("42 U.S.C.")
    assert len(payload["cases"]) == 2
    assert result.metadata["case_count"] == 2
    assert result.metadata["statute_id"] == "statute:us:section:1983"


def test_courtlistener_statute_follow_builder_limits_cases() -> None:
    artifact = build_courtlistener_statute_case_follow("statute:us:section:1983", limit=1)
    assert artifact["artifact_role"] == "derived_product"
    assert artifact["lineage"]["upstream_artifact_ids"] == ["statute:us:section:1983"]
    assert artifact["summary"]["case_count"] == 1
    assert artifact["cases"][0]["case_id"] == "cl:us:marbury_v_madison"
    assert artifact["follow_obligation"]["scope"] == "bounded_case_law_follow"
    assert artifact["metadata"]["statute_url"].startswith("https://")
