from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("dbpedia_lookup_api", str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_emit_batch_payload_accepts_pick_and_anchors() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "dbpedia_lookup_api.py"
    ).resolve()
    mod = _load_module(script)

    rows = [
        {
            "uri": "http://dbpedia.org/resource/Westmead_Hospital",
            "label": "Westmead Hospital",
            "comment": "Westmead Hospital is a major tertiary hospital in Sydney, Australia.",
            "types": ["http://dbpedia.org/ontology/Hospital"],
        }
    ]

    payload = mod._external_refs_batch_payload(  # type: ignore[attr-defined]
        term="Westmead Hospital",
        url="http://lookup.dbpedia.org/api/search?format=JSON&query=Westmead+Hospital&maxResults=5",
        rows=rows,
        pick=1,
        actor_id=42,
        concept_code="HOSPITAL",
    )

    assert "meta" in payload
    assert payload["actor_external_refs"][0]["actor_id"] == 42
    assert payload["concept_external_refs"][0]["concept_code"] == "HOSPITAL"
    assert payload["actor_external_refs"][0]["external_id"].endswith("Westmead_Hospital")


def test_emit_batch_payload_rejects_out_of_range_pick() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "dbpedia_lookup_api.py"
    ).resolve()
    mod = _load_module(script)

    rows = [{"uri": "http://dbpedia.org/resource/X", "label": "X", "comment": None, "types": []}]
    try:
        mod._external_refs_batch_payload(  # type: ignore[attr-defined]
            term="X",
            url="http://lookup.dbpedia.org/api/search?format=JSON&query=X&maxResults=1",
            rows=rows,
            pick=2,
            actor_id=1,
            concept_code=None,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for out-of-range pick")

