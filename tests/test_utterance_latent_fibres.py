from __future__ import annotations

import json
from pathlib import Path

from src.text.residual_lattice import PredicateAtom, QualifierState, ResidualLevel, TypedArg, meet_atom
from src.text.utterance_latent_fibres import (
    LATENT_FIBRE_INDEX_SCHEMA,
    enrich_utterance_atoms,
    load_latent_index,
    meet_atom_with_latent_fibres,
    parse_latent_index,
)
from scripts.build_utterance_latent_fibres import build_artifact


def _artifact() -> dict:
    return {
        "artifact_id": "fixture-local-corpus-v1",
        "schema_version": LATENT_FIBRE_INDEX_SCHEMA,
        "source_corpus": {
            "manifest_id": "fixture-corpus",
            "manifest_hash": "sha256:fixture-corpus-hash",
        },
        "extraction_profile": {
            "name": "fixture-pnf-cooccurrence",
            "version": "v1",
        },
        "model_assets": [
            {
                "asset_id": "future-spacy-vector-export",
                "kind": "offline_vector_export",
                "sha256": "sha256:model-placeholder",
                "status": "documented_future_compatible",
            }
        ],
        "predicate_nodes": {
            "amble": {"observation_count": 4},
            "stride": {"observation_count": 5},
            "ignite": {"observation_count": 1},
        },
        "role_context_signatures": {
            "person_path": {
                "signature": "object:path|subject:person",
                "evidence_refs": ["obs:1", "obs:2"],
            }
        },
        "derived_fibre_candidates": [
            {
                "candidate_id": "fibre:stride-amble:canonical",
                "source_predicate": "stride",
                "target_predicate": "amble",
                "relation": "same_family_candidate",
                "confidence": 0.91,
                "evidence_count": 4,
                "signal_count": 2,
                "evidence_refs": ["obs:1", "obs:2", "obs:3", "obs:4"],
                "provenance_refs": ["corpus:fixture:1"],
                "role_context_signatures": ["object:path|subject:person"],
                "high_precision": True,
                "canonical": True,
            },
            {
                "candidate_id": "fibre:stride-ignite:weak",
                "source_predicate": "stride",
                "target_predicate": "ignite",
                "relation": "diagnostic_neighbour",
                "confidence": 0.72,
                "evidence_count": 1,
                "signal_count": 1,
                "evidence_refs": ["obs:weak"],
                "diagnostics_only": True,
                "canonical": False,
            },
        ],
    }


def _utterance(predicate: str, polarity: str = "positive", obj: str = "trail") -> PredicateAtom:
    return PredicateAtom(
        predicate=predicate,
        structural_signature=f"utterance_event:{predicate}",
        roles={
            "action": TypedArg(value=predicate, entity_type="action"),
            "subject": TypedArg(value="walker", entity_type="person"),
            "object": TypedArg(value=obj, entity_type="path"),
        },
        qualifiers=QualifierState(polarity=polarity),
        provenance=(f"doc:{predicate}",),
        atom_id=f"atom:{predicate}",
        domain="utterance_event",
    )


def test_latent_index_loads_deterministically_and_preserves_provenance(tmp_path: Path) -> None:
    artifact_path = tmp_path / "latent.json"
    artifact_path.write_text(json.dumps(_artifact(), sort_keys=True), encoding="utf-8")

    index = load_latent_index(artifact_path)

    assert index.artifact_id == "fixture-local-corpus-v1"
    assert index.source_corpus["manifest_hash"] == "sha256:fixture-corpus-hash"
    assert [candidate.candidate_id for candidate in index.candidates] == [
        "fibre:stride-amble:canonical",
        "fibre:stride-ignite:weak",
    ]
    assert index.candidates[0].provenance_refs == ("corpus:fixture:1",)
    assert index.artifact_sha256


def test_parse_rejects_missing_manifest_hash() -> None:
    payload = _artifact()
    payload["source_corpus"] = {"manifest_id": "fixture-corpus"}

    try:
        parse_latent_index(payload)
    except ValueError as exc:
        assert "source_corpus.manifest_hash" in str(exc)
    else:
        raise AssertionError("expected manifest hash validation failure")


def test_checked_in_default_artifact_loads() -> None:
    index = load_latent_index("data/latent_fibres/utterance_latent_fibres.v0_1.json")

    assert index.schema_version == LATENT_FIBRE_INDEX_SCHEMA
    assert index.artifact_id == "sensiblaw-utterance-latent-fibres-v0_1"
    assert index.source_corpus["manifest_hash"]


def test_builder_emits_schema_valid_deterministic_artifact(tmp_path: Path) -> None:
    manifest = {
        "text": "I walked the dog. I ambled the dog.",
        "latent_fibre_candidates": [
            {
                "source_predicate": "walk",
                "target_predicate": "amble",
                "confidence": 0.9,
                "evidence_count": 2,
                "signal_count": 2,
                "evidence_refs": ["obs:walk", "obs:amble"],
                "provenance_refs": ["manifest:fixture"],
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    left = build_artifact(manifests=[manifest_path], corpora=[])
    right = build_artifact(manifests=[manifest_path], corpora=[])

    assert left == right
    index = parse_latent_index(left)
    assert index.candidates[0].candidate_id == "fibre:walk-amble:canonical"
    assert index.source_corpus["manifest_hash"].startswith("sha256:")


def test_builder_generates_cooccurrence_candidates_from_corpus(tmp_path: Path) -> None:
    manifest = {
        "text": "I publish the update and check the update.",
    }
    corpus_path = tmp_path / "corpus.txt"
    corpus_path.write_text(
        "I publish the update and she checks the updates every quarter.\n",
        encoding="utf-8",
    )
    corpus_path_2 = tmp_path / "corpus2.txt"
    corpus_path_2.write_text("I checked the update and they publish the update.\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    artifact = build_artifact(
        manifests=[manifest_path],
        corpora=[corpus_path, corpus_path_2],
        min_evidence_count=2,
        min_signal_count=1,
        min_confidence=0.0,
    )
    index = parse_latent_index(artifact)

    cooccurrence = [candidate for candidate in index.candidates if "cooccurrence_generator:v1" in candidate.model_refs]
    assert cooccurrence
    pair = {(candidate.source_predicate, candidate.target_predicate) for candidate in cooccurrence}
    assert ("publish", "check") in pair or ("check", "publish") in pair
    assert all(candidate.canonical for candidate in cooccurrence)


def test_enrich_emits_only_corpus_supported_canonical_fibres() -> None:
    index = parse_latent_index(_artifact())

    enriched = enrich_utterance_atoms([_utterance("stride"), _utterance("ignite")], index)

    assert enriched[0].semantic_comparison_mode == "latent_candidate"
    assert enriched[0].support_fibres[0]["candidate_id"] == "fibre:stride-amble:canonical"
    assert enriched[0].latent_grounding["artifact_id"] == "fixture-local-corpus-v1"
    assert enriched[1].semantic_comparison_mode == "abstained"
    assert enriched[1].support_fibres == ()
    assert enriched[1].latent_grounding["abstention_reason"] == "no_supported_latent_fibre"


def test_exact_structural_signature_still_wins_without_latent_path() -> None:
    left = _utterance("stride")
    right = _utterance("stride")
    index = parse_latent_index(_artifact())

    assert meet_atom(left, right).level is ResidualLevel.EXACT
    residual = meet_atom_with_latent_fibres(left, right, index)

    assert residual.level is ResidualLevel.EXACT
    assert residual.semantic_comparison_mode == "exact"


def test_latent_candidate_produces_partial_same_family_residual() -> None:
    index = parse_latent_index(_artifact())

    residual = meet_atom_with_latent_fibres(_utterance("stride"), _utterance("amble"), index)

    assert residual.level is ResidualLevel.PARTIAL
    assert residual.semantic_comparison_mode == "latent_candidate"
    assert residual.semantic_relation == "same_family_candidate"
    assert residual.latent_grounding["candidate_refs"] == ["fibre:stride-amble:canonical"]
    assert residual.provenance == ("corpus:fixture:1",)


def test_weak_single_signal_evidence_does_not_affect_canonical_comparison() -> None:
    index = parse_latent_index(_artifact())

    residual = meet_atom_with_latent_fibres(_utterance("stride"), _utterance("ignite"), index)

    assert residual.level is ResidualLevel.NO_TYPED_MEET
    assert residual.semantic_comparison_mode == "abstained"
    assert residual.latent_grounding["abstention_reason"] == "no_supported_pair_fibre"


def test_context_mismatch_blocks_contradiction_promotion() -> None:
    index = parse_latent_index(_artifact())

    residual = meet_atom_with_latent_fibres(
        _utterance("stride", polarity="positive", obj="trail"),
        _utterance("amble", polarity="negative", obj="brief"),
        index,
    )

    assert residual.level is ResidualLevel.NO_TYPED_MEET
    assert residual.semantic_comparison_mode == "abstained"
    assert residual.latent_grounding["abstention_reason"] == "role_context_incompatible"


def test_polarity_conflict_promotes_only_for_high_precision_context_support() -> None:
    index = parse_latent_index(_artifact())

    residual = meet_atom_with_latent_fibres(
        _utterance("stride", polarity="positive"),
        _utterance("amble", polarity="negative"),
        index,
    )

    assert residual.level is ResidualLevel.CONTRADICTION
    assert residual.contradictions == ("polarity conflict across supported latent fibre",)
    assert residual.semantic_comparison_mode == "latent_candidate"


def test_runtime_has_no_fixture_specific_verb_family_mapping() -> None:
    runtime = Path("src/text/utterance_latent_fibres.py").read_text(encoding="utf-8")

    assert "stride': 'amble" not in runtime
    assert "amble': 'stride" not in runtime
    assert "run ~= walk" not in runtime
