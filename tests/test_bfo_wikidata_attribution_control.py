import json
from pathlib import Path

from src.ontology.wikidata_contradiction_attribution import (
    EvidenceSquare,
    LayerEvidence,
    build_cross_ontology_attribution,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "data" / "ontology" / "bfo_wikidata_continuant_occurrent_attribution_v1.json"


def _layer(raw):
    return LayerEvidence(
        EvidenceSquare(bool(raw.get("supports")), bool(raw.get("refutes"))),
        evidence=tuple(raw.get("evidence", [])),
        provenance=tuple(raw.get("provenance", [])),
        obligations=tuple(raw.get("obligations", [])),
    )


def test_bfo_continuant_occurrent_control_does_not_manufacture_target_conflict() -> None:
    raw = json.loads(PACKET.read_text(encoding="utf-8"))
    packet = build_cross_ontology_attribution(
        claim_id=raw["claim_id"],
        claim_surface=raw["claim_surface"],
        source=_layer(raw["source"]),
        transcription=_layer(raw["transcription"]),
        alignment=_layer(raw["alignment"]),
        target=_layer(raw["target"]),
        required_layers=tuple(raw["required_layers"]),
    )

    assert raw["source_snapshot"]["commit"] == "0900316ea9d330f599bd110f7f6504ed33a87fc8"
    assert raw["wikidata_mapping_snapshot"]["continuant"] == {
        "qid": "Q103940464",
        "bfo_id": "0000002",
    }
    assert raw["wikidata_mapping_snapshot"]["occurrent"] == {
        "qid": "Q67518978",
        "bfo_id": "0000003",
    }
    assert packet["layers"]["source"]["corner"] == "support-only"
    assert packet["layers"]["transcription"]["corner"] == "support-only"
    assert packet["layers"]["alignment"]["corner"] == "neither"
    assert packet["layers"]["target"]["corner"] == "neither"
    assert packet["required_resolution"] == "unresolved-required-axis"
