from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.legal_edge_admissibility import (
    LEGAL_EDGE_ADMISSIBILITY_VERSION,
    evaluate_legal_edge_admissibility,
    gate_legal_edge_admissibility,
)


@dataclass
class _PayloadStub:
    payload: dict

    def to_dict(self) -> dict:
        return dict(self.payload)


def _endpoint(
    *,
    decision: str = "promote",
    status: str = "promoted",
    wrapper_kind: str = "authority_wrapper",
    wrapper_status: str = "valid",
    section: str = "Judgment",
    genre: str = "case",
    support_phi_ids: list[str] | None = None,
    content_refs: list[str] | None = None,
    span_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "decision": decision,
        "node": {
            "status": status,
            "section": section,
            "genre": genre,
            "support_phi_ids": list(support_phi_ids or ["phi:1"]),
            "content_refs": list(content_refs or ["cr:1"]),
            "span_refs": list(span_refs or ["span:1"]),
            "authority_wrapper": {
                "wrapper_kind": wrapper_kind,
                "status": wrapper_status,
            },
        },
    }


def _edge_payload(
    *,
    relation_kind: str = "supports",
    source: dict[str, object] | None = None,
    target: dict[str, object] | None = None,
    shared_support_linkage: dict[str, object] | None = None,
    section_genre_compatibility: dict[str, object] | None = None,
    section: str = "Judgment",
    genre: str = "case",
) -> dict[str, object]:
    return {
        "relation_kind": relation_kind,
        "source_node_admissibility": source or _endpoint(),
        "target_node_admissibility": target or _endpoint(),
        "shared_support_linkage": shared_support_linkage
        or {
            "support_phi_ids": ["phi:1"],
            "content_refs": ["cr:1"],
            "span_refs": ["span:1"],
        },
        "section_genre_compatibility": section_genre_compatibility
        or {"status": "compatible", "section": section, "genre": genre},
        "section": section,
        "genre": genre,
    }


def test_gate_promotes_for_supported_relation_with_shared_linkage_and_compatible_endpoints() -> None:
    result = evaluate_legal_edge_admissibility(_PayloadStub(_edge_payload()))

    assert result["version"] == LEGAL_EDGE_ADMISSIBILITY_VERSION
    assert result["decision"] == "promote"
    assert result["reasons"] == []
    assert result["checks"] == {
        "relation_kind_supported": True,
        "source_endpoint_admissible": True,
        "target_endpoint_admissible": True,
        "wrapper_compatible": True,
        "section_genre_compatible": True,
        "shared_support_linkage_present": True,
    }


def test_gate_audits_when_shared_support_linkage_witness_is_missing() -> None:
    payload = _edge_payload()
    payload.pop("shared_support_linkage")

    result = gate_legal_edge_admissibility(payload)

    assert result["decision"] == "audit"
    assert "missing_shared_support_linkage" in result["reasons"]


def test_gate_abstains_when_relation_kind_is_unsupported() -> None:
    payload = _edge_payload(relation_kind="lexical_hint")

    result = evaluate_legal_edge_admissibility(payload)

    assert result["decision"] == "abstain"
    assert any("unsupported_relation_kind" in reason for reason in result["reasons"])


def test_gate_abstains_when_source_endpoint_is_abstain() -> None:
    payload = _edge_payload(source=_endpoint(decision="abstain"))

    result = evaluate_legal_edge_admissibility(payload)

    assert result["decision"] == "abstain"
    assert "source_endpoint_abstain" in result["reasons"]


def test_gate_abstains_when_section_genre_is_explicitly_incompatible() -> None:
    payload = _edge_payload(
        section_genre_compatibility={"status": "incompatible", "section": "Judgment", "genre": "case"}
    )

    result = evaluate_legal_edge_admissibility(payload)

    assert result["decision"] == "abstain"
    assert "section_genre_incompatible" in result["reasons"]


def test_gate_abstains_when_contradiction_lacks_structural_status_conflict() -> None:
    payload = _edge_payload(
        relation_kind="contradicts",
        source=_endpoint(status="ruled", content_refs=["cr:shared"]),
        target=_endpoint(status="ruled", content_refs=["cr:shared"]),
        shared_support_linkage={"content_refs": ["cr:shared"]},
    )

    result = evaluate_legal_edge_admissibility(payload)

    assert result["decision"] == "abstain"
    assert "status_conflict_required" in result["reasons"]


def test_gate_promotes_for_contradiction_when_status_conflict_is_structural() -> None:
    payload = _edge_payload(
        relation_kind="contradicts",
        source=_endpoint(status="ruled", content_refs=["cr:shared"], support_phi_ids=["phi:shared"]),
        target=_endpoint(status="denied", content_refs=["cr:shared"], support_phi_ids=["phi:shared"]),
        shared_support_linkage={"content_refs": ["cr:shared"], "support_phi_ids": ["phi:shared"]},
    )

    result = evaluate_legal_edge_admissibility(payload)

    assert result["decision"] == "promote"
    assert result["checks"]["shared_support_linkage_present"] is True

