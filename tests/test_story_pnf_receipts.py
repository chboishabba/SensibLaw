from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.sensiblaw.interfaces import (
    CLASSIFICATION_DISCOVERY_LATTICE_SCHEMA,
    AUTHORITY_BOUNDARY,
    STORY_PNF_RECEIPTS_SCHEMA,
    SUPPORTED_SOURCE_PROFILES,
    collect_canonical_story_pnf_receipts,
    render_classification_discovery_lattice_png,
)


def _collect_chain_payload(
    text: str,
    *,
    class_relation_witnesses: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
) -> dict[str, object]:
    payload = collect_canonical_story_pnf_receipts(
        text,
        source_profile="conversation_text",
        source_id="classification-story",
        class_relation_witnesses=class_relation_witnesses or [],
    )
    assert payload["classification_lattice"] is not None
    return payload


@pytest.mark.parametrize(
    ("profile", "source", "expected_families"),
    [
        (
            "conversation_text",
            "Alex: I promise to follow the authority.\nBlair: I denied the allegation.",
            {"context/frame", "sequence/event", "claim/assertion", "commitment/lifecycle"},
        ),
        (
            "story_event",
            [{"event_id": "e1", "timestamp": "2026-06-05T09:00:00Z", "actor": "TiRCorder", "action": "captured", "details": "observed filing"}],
            {"context/frame", "sequence/event", "observer/evidence", "claim/assertion"},
        ),
        (
            "observer_capture",
            [{"timestamp": "2026-06-05T09:01:00Z", "device": "laptop", "session": "s1", "window_title": "Court portal", "ocr_text": "observed order"}],
            {"context/frame", "sequence/event", "observer/evidence", "claim/assertion"},
        ),
        (
            "execution_envelope",
            [{"command": "pytest", "status": "done", "log": "tests passed", "task": "suite pnf"}],
            {"context/frame", "sequence/event", "commitment/lifecycle"},
        ),
        (
            "fact_review_item",
            [{"source": "doc-a", "statement": "The filing was sourced.", "review_status": "candidate"}],
            {"context/frame", "epistemic/status", "claim/assertion"},
        ),
        (
            "handoff_entry",
            [{"recipient": "lawyer", "scope": "professional", "redaction_marker": "protected", "details": "private protected disclosure text"}],
            {"context/frame", "scope/boundary", "handoff/export"},
        ),
    ],
)
def test_collect_canonical_story_pnf_receipts_profile_matrix(
    profile: str,
    source: object,
    expected_families: set[str],
) -> None:
    payload = collect_canonical_story_pnf_receipts(
        source,
        source_profile=profile,
        source_id=f"src-{profile}",
        context={"medium": profile, "audience": "suite-test", "session": "s1"},
    )

    assert payload["schema"] == STORY_PNF_RECEIPTS_SCHEMA
    assert payload["authority_boundary"] == AUTHORITY_BOUNDARY
    assert payload["emission_receipts"]
    assert payload["residual_receipts"]

    families = {receipt["predicate_family"] for receipt in payload["emission_receipts"]}
    assert expected_families <= families
    assert all(receipt["emitted_atom"]["wrapper"]["evidence_only"] is True for receipt in payload["emission_receipts"])
    assert all(receipt["authority_boundary"] == AUTHORITY_BOUNDARY for receipt in payload["emission_receipts"])


def test_story_pnf_residuals_cover_exact_partial_contradiction_and_no_typed_meet() -> None:
    source = [
        {"_row_ref": "run-1", "actor": "builder", "action": "executed", "object": "tests", "status": "done"},
        {"_row_ref": "run-1", "actor": "builder", "action": "executed", "status": "done"},
        {"_row_ref": "run-1", "scope": "work"},
        {"_row_ref": "run-1", "scope": "home"},
    ]

    payload = collect_canonical_story_pnf_receipts(
        source,
        source_profile="execution_envelope",
        source_id="sb-run",
    )

    summary = payload["residual_summary"]
    assert summary["exact"] > 0
    assert summary["partial"] > 0
    assert summary["contradiction"] > 0
    assert summary["no_typed_meet"] > 0


def test_story_pnf_receipts_minimize_sensitive_handoff_fields() -> None:
    secret = "private protected disclosure text that must not be replayed verbatim"

    payload = collect_canonical_story_pnf_receipts(
        [{"recipient": "professional", "scope": "private", "details": secret}],
        source_profile="handoff_entry",
        source_id="handoff-1",
    )

    serialized = json.dumps(payload, sort_keys=True)
    assert secret not in serialized
    assert "sha256" in serialized
    assert all(
        receipt["payload"]["authority_boundary"] == AUTHORITY_BOUNDARY
        for receipt in payload["residual_receipts"]
    )


def test_story_pnf_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unsupported source_profile"):
        collect_canonical_story_pnf_receipts({}, source_profile="unknown")


def test_story_pnf_supported_profiles_match_v1_contract() -> None:
    assert SUPPORTED_SOURCE_PROFILES == {
        "conversation_text",
        "story_event",
        "observer_capture",
        "execution_envelope",
        "fact_review_item",
        "handoff_entry",
    }


def test_classification_chain_builds_discovery_lattice_without_contradiction() -> None:
    payload = _collect_chain_payload(
        "6 is a 1-morphism, 6 is a 2-morphism, 6 is a j-invariant, 6 is a dolphin."
    )
    lattice = payload["classification_lattice"]
    assert isinstance(lattice, dict)
    assert lattice["schema"] == CLASSIFICATION_DISCOVERY_LATTICE_SCHEMA

    classified_as = [edge for edge in lattice["edges"] if edge["type"] == "classified_as"]
    reclass = [edge for edge in lattice["edges"] if edge["type"] == "discovery_reclassification"]
    assert len(classified_as) == 4
    assert len(reclass) == 3
    assert all(edge["relation_type"] == "same" for edge in classified_as)
    assert all(edge["relation_root"] == "supports" for edge in classified_as)
    assert all(edge["relation_basis"] == "explicit_claim" for edge in classified_as)
    assert {edge["classification_claim_root"] for edge in classified_as} >= {
        "morphism",
        "algebraic_geometry",
        "biological_taxon",
    }
    assert all(item["status"] != "exclusive_contradiction" for item in classified_as)
    assert all(item["residual_level"] != "contradiction" for item in lattice.get("residual_receipts", []))


def test_classification_positive_and_negative_same_subject_class_is_core_contradiction() -> None:
    payload = _collect_chain_payload("6 is a dolphin, 6 is not a dolphin.")
    lattice = payload["classification_lattice"]
    assert lattice["residual_receipts"]
    assert any(
        item["status"] == "exclusive_contradiction" and item["residual_level"] == "contradiction"
        for item in lattice.get("residual_receipts", [])
    )


def test_refinement_and_domain_bridge_witnesses_influence_lattice_statuses() -> None:
    payload = _collect_chain_payload(
        "6 is a 1-morphism. 6 is a 2-morphism.",
        class_relation_witnesses=[
            {
                "from_class": "1-morphism",
                "to_class": "2-morphism",
                "relation": "refines",
            }
        ],
    )
    lattice = payload["classification_lattice"]
    statuses = {edge["status"] for edge in lattice["edges"] if edge["type"] == "class_relation"}
    assert "refinement_candidate" in statuses
    refinement_edges = [
        edge
        for edge in lattice["edges"]
        if edge["type"] == "class_relation" and edge["status"] == "refinement_candidate"
    ]
    assert refinement_edges
    assert refinement_edges[0]["relation_type"] == "refines"
    assert refinement_edges[0]["relation_root"] == "supports"
    assert refinement_edges[0]["relation_basis"] == "explicit_witness"

    payload_without_witness = _collect_chain_payload("6 is a j-invariant. 6 is a dolphin.")
    lattice_without = payload_without_witness["classification_lattice"]
    statuses_without = {
        edge["status"] for edge in lattice_without["edges"] if edge["type"] == "class_relation"
    }
    assert "cross_domain_gap" in statuses_without
    gap_edges = [
        edge
        for edge in lattice_without["edges"]
        if edge["type"] == "class_relation" and edge["status"] == "cross_domain_gap"
    ]
    assert gap_edges
    assert gap_edges[0]["relation_type"] == "domain_gap"
    assert gap_edges[0]["relation_root"] == "non_resolving"
    assert gap_edges[0]["relation_basis"] == "domain_heuristic"

    payload_exclusive = _collect_chain_payload(
        "6 is a 1-morphism. 6 is a dolphin.",
        class_relation_witnesses=[
            {
                "from_class": "morphism",
                "to_class": "dolphin",
                "relation": "domain_exclusion",
                "strength": "strong",
            }
        ],
    )
    lattice_exclusive = payload_exclusive["classification_lattice"]
    class_statuses = {edge["status"] for edge in lattice_exclusive["edges"] if edge["type"] == "class_relation"}
    assert "exclusive_contradiction" in class_statuses
    exclusive_edges = [
        edge
        for edge in lattice_exclusive["edges"]
        if edge["type"] == "class_relation" and edge["status"] == "exclusive_contradiction"
    ]
    assert exclusive_edges
    assert exclusive_edges[0]["relation_type"] == "excluded_by_witness"
    assert exclusive_edges[0]["relation_root"] == "invalidates"
    assert exclusive_edges[0]["relation_basis"] == "explicit_witness"

    payload_weak = _collect_chain_payload(
        "6 is a 1-morphism. 6 is a dolphin.",
        class_relation_witnesses=[
            {
                "from_class": "morphism",
                "to_class": "dolphin",
                "relation": "domain_exclusion",
                "strength": "possible",
            }
        ],
    )
    lattice_weak = payload_weak["classification_lattice"]
    class_statuses_weak = {
        edge["status"] for edge in lattice_weak["edges"] if edge["type"] == "class_relation"
    }
    assert "unsupported_out_of_domain_candidate" in class_statuses_weak


def test_alias_witness_collapses_equivalent_class_labels() -> None:
    payload = _collect_chain_payload(
        "6 is a 1-morphism. 6 is a morphism.",
        class_relation_witnesses=[
            {
                "from_class": "1-morphism",
                "to_class": "morphism",
                "relation": "alias",
            }
        ],
    )
    lattice = payload["classification_lattice"]
    class_nodes = [node["value"] for node in lattice["nodes"] if node["kind"] == "class"]
    assert len(set(class_nodes)) == 1


def test_classification_lattice_visualization_payload_is_stable_and_renders_png(
    tmp_path: Path,
) -> None:
    payload = _collect_chain_payload(
        "6 is a 1-morphism. 6 is a 2-morphism. 6 is a j-invariant. 6 is a dolphin."
    )
    lattice = payload["classification_lattice"]
    assert any(node["kind"] == "classification_claim_root" for node in lattice["nodes"])
    assert any(node["kind"] == "classification_leaf" for node in lattice["nodes"])
    assert len(lattice["edges"]) >= 19

    first = tmp_path / "chain.png"
    second = tmp_path / "chain-repeat.png"
    render_classification_discovery_lattice_png(lattice, first)
    render_classification_discovery_lattice_png(lattice, second)
    assert first.stat().st_size > 0
    assert second.stat().st_size > 0
    assert first.read_bytes() == second.read_bytes()
