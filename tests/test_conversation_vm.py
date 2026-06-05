from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sensiblaw.conversation_vm import (  # type: ignore[import-not-found]
    CONTEXT_PAYLOAD_SCHEMA,
    PROOF_SURFACE_SCHEMA,
    STATE_SCHEMA,
    TURN_DELTA_SCHEMA,
    build_context_payload,
    build_proof_surface,
    compile_turn,
    empty_state,
    step_state,
)
import src.sensiblaw.interfaces.shared_reducer as shared_reducer
from src.sensiblaw.conversation_vm.compiler import reset_projector_cache_for_tests
from src.text import LATENT_FIBRE_INDEX_SCHEMA


def test_compile_turn_preserves_receipted_source_surfaces_and_is_deterministic() -> None:
    turn = {
        "turn_id": "fixture-turn-1",
        "text": "Alpha supports beta. No alpha supports beta.",
        "fact_candidates": [{"kind": "candidate-fact", "text": "Alpha supports beta."}],
    }

    left = compile_turn(turn)
    right = compile_turn(turn)

    assert left == right
    assert left["schema"] == TURN_DELTA_SCHEMA
    assert left["sources"][0]["text"] == turn["text"]
    assert left["excerpts"][0]["text"] == "Alpha supports beta."
    assert left["statements"][0]["receipt_ids"]
    assert left["observations"][0]["status"] == "supported"
    assert left["predicate_atoms"]
    assert left["predicate_pnfs"]
    assert all(
            atom["projection_method"]
            in {
                "sensiblaw.shared_reducer.collect_canonical_predicate_atoms",
                "sensiblaw.shared_reducer.collect_canonical_relational_bundle",
                "conversation_vm_structural_parser",
            }
        for atom in left["predicate_atoms"]
    )


def test_compile_turn_uses_shared_reducer_head_as_predicate_when_available() -> None:
    reset_projector_cache_for_tests()

    delta = compile_turn({"turn_id": "typed-projection", "text": "Leader publishes transactions."})

    predicates = {atom["predicate"] for atom in delta["predicate_atoms"]}
    assert "publish" in predicates
    assert "predicate" not in predicates
    assert any(atom["projection_method"] == "sensiblaw.shared_reducer.collect_canonical_predicate_atoms" for atom in delta["predicate_atoms"])


def test_compile_turn_preserves_utterance_pnf_roles_and_qualifiers() -> None:
    reset_projector_cache_for_tests()

    delta = compile_turn({"turn_id": "utterance-pnf", "text": "I did not walk the dog."})

    atom = delta["predicate_atoms"][0]
    assert atom["predicate"] == "walk"
    assert atom["arguments"] == ["i", "dog"]
    assert atom["polarity"] == "negative"
    assert atom["structural_signature"] == "utterance_event:walk"
    assert atom["domain"] == "utterance_event"
    assert atom["roles"]["subject"]["value"] == "i"
    assert atom["roles"]["object"]["value"] == "dog"
    assert atom["roles"]["action"]["value"] == "walk"
    assert atom["qualifiers"]["polarity"] == "negative"
    assert delta["predicate_pnfs"][0]["normal_form"]["roles"]["object"]["value"] == "dog"


def test_compile_turn_emits_pnf_receipts_for_copular_classification_tension() -> None:
    reset_projector_cache_for_tests()

    delta = compile_turn({"turn_id": "copular-pnf", "text": "6 is a 1-morphism, not an object."})

    classification_atoms = [atom for atom in delta["predicate_atoms"] if atom["predicate"] == "be/classify"]
    assert len(classification_atoms) == 2
    assert {(atom["roles"]["theme"]["value"], atom["polarity"]) for atom in classification_atoms} == {
        ("1-morphism", "positive"),
        ("object", "negative"),
    }
    contested = [item for item in delta["residual_comparisons"] if item["relation"] == "classification-tension"]
    assert len(contested) == 1
    assert contested[0]["residual_level"] == "contradiction"
    assert delta["pnf_emission_receipts"]
    residual_receipts = [item for item in delta["pnf_residual_receipts"] if item["relation"] == "classification-tension"]
    assert len(residual_receipts) == 1
    assert residual_receipts[0]["left_emission_receipt_id"]
    assert residual_receipts[0]["right_emission_receipt_id"]
    assert residual_receipts[0]["payload"]["runtime_provider_status"] == "missingHeckeCandidatePoolReceiptId"


def _latent_fibre_artifact(path: Path) -> Path:
    payload = {
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
        "model_assets": [],
        "predicate_nodes": {"walk": {"observation_count": 4}},
        "role_context_signatures": {},
        "derived_fibre_candidates": [
            {
                "candidate_id": "fibre:walk-amble:canonical",
                "source_predicate": "walk",
                "target_predicate": "amble",
                "relation": "same_family_candidate",
                "confidence": 0.91,
                "evidence_count": 4,
                "signal_count": 2,
                "evidence_refs": ["obs:1", "obs:2", "obs:3", "obs:4"],
                "provenance_refs": ["corpus:fixture:1"],
                "canonical": True,
            }
        ],
    }
    artifact_path = path / "utterance-latent-fibres.json"
    artifact_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return artifact_path


def test_compile_turn_enriches_predicate_atoms_from_env_seeded_latent_fibre_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_path = _latent_fibre_artifact(tmp_path)
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH", str(artifact_path))
    reset_projector_cache_for_tests()

    delta = compile_turn({"turn_id": "latent-turn", "text": "I walked the dog."})

    assert delta["predicate_atoms"]
    atom = delta["predicate_atoms"][0]
    assert atom["semantic_comparison_mode"] == "latent_candidate"
    assert atom["support_fibres"]
    assert atom["latent_grounding"]["artifact_id"] == "fixture-local-corpus-v1"
    assert delta["predicate_pnfs"][0]["normal_form"]["semantic_comparison_mode"] == "latent_candidate"
    assert delta["predicate_pnfs"][0]["normal_form"]["support_fibres"]
    assert delta["predicate_pnfs"][0]["normal_form"]["latent_grounding"]["artifact_id"] == "fixture-local-corpus-v1"


def test_compile_turn_selects_latent_fibre_index_from_config_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_path = _latent_fibre_artifact(tmp_path)
    config_path = tmp_path / "latent-config.json"
    config_path.write_text(
        json.dumps(
            {
                "utterance_latent_fibre_index_path": str(artifact_path),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG", str(config_path))
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH", "")
    shared_reducer._clear_utterance_latent_fibre_index_cache()
    reset_projector_cache_for_tests()

    delta = compile_turn({"turn_id": "latent-turn-config", "text": "I walked the dog."})

    assert delta["predicate_atoms"]
    atom = delta["predicate_atoms"][0]
    assert atom["semantic_comparison_mode"] == "latent_candidate"
    assert atom["latent_grounding"]["artifact_id"] == "fixture-local-corpus-v1"


def test_state_join_preserves_supported_receipts() -> None:
    delta = compile_turn(
        {
            "turn_id": "supported-turn",
            "text": "Alpha supports beta.",
            "fact_candidates": [{"kind": "candidate-fact", "text": "Alpha supports beta."}],
        }
    )

    state = step_state(empty_state(), delta)

    assert state["schema"] == STATE_SCHEMA
    assert state["observations"][0]["status"] == "supported"
    assert state["observations"][0]["receipt_ids"]
    assert state["status_history"]


def test_cross_turn_contradiction_adds_contested_without_deleting_support() -> None:
    positive = {
        "id": "delta-positive",
        "predicate_atoms": [
            {
                "id": "atom-positive",
                "predicate": "claim",
                "arguments": ["alpha"],
                "polarity": "positive",
                "status": "supported",
                "receipt_ids": ["receipt-positive"],
            }
        ],
    }
    negative = {
        "id": "delta-negative",
        "predicate_atoms": [
            {
                "id": "atom-negative",
                "predicate": "claim",
                "arguments": ["alpha"],
                "polarity": "negative",
                "status": "supported",
                "receipt_ids": ["receipt-negative"],
            }
        ],
    }

    state = step_state(step_state(empty_state(), positive), negative)

    assert len(state["predicate_atoms"]) == 2
    assert state["contested_items"]
    assert state["residual_comparisons"][0]["status"] == "contested"
    receipts = set(state["residual_comparisons"][0]["receipt_ids"])
    assert {"receipt-positive", "receipt-negative"} <= receipts


def test_cross_turn_utterance_pnf_sign_conflict_adds_contested_item() -> None:
    reset_projector_cache_for_tests()

    state = empty_state()
    state = step_state(state, compile_turn({"turn_id": "walk-positive", "text": "I walked the dog."}))
    state = step_state(state, compile_turn({"turn_id": "walk-negative", "text": "I did not walk the dog."}))

    assert state["contested_items"]
    assert state["residual_comparisons"][0]["relation"] == "polarity-conflict"
    assert state["residual_comparisons"][0]["status"] == "contested"


def test_abstained_no_typed_meet_remains_visible() -> None:
    delta = {
        "id": "delta-abstain",
        "abstentions": [
            {
                "id": "abstain-no-meet",
                "status": "abstained",
                "reason": "no-typed-meet",
                "receipt_ids": ["receipt-a"],
            }
        ],
    }

    state = step_state(empty_state(), delta)
    payload = build_context_payload(state)

    assert payload["schema"] == CONTEXT_PAYLOAD_SCHEMA
    assert payload["abstentions"][0]["reason"] == "no-typed-meet"


def test_promotion_without_required_receipts_is_blocked() -> None:
    delta = {
        "id": "delta-promoted-without-receipts",
        "predicate_atoms": [
            {
                "id": "atom-promoted",
                "predicate": "claim",
                "arguments": ["alpha"],
                "polarity": "positive",
                "status": "promoted",
                "receipt_ids": [],
            }
        ],
        "promotion_gates": [
            {
                "id": "gate-source",
                "name": "source_receipt",
                "status": "blocked",
                "receipt_ids": [],
            }
        ],
    }

    state = step_state(empty_state(), delta)

    assert state["blockers"]
    assert state["blockers"][0]["atom_id"] == "atom-promoted"
    assert "source_receipt" in state["blockers"][0]["missing_gates"]


def test_proof_and_context_payloads_preserve_provenance_not_opaque_summary() -> None:
    state = step_state(empty_state(), compile_turn({"turn_id": "query-turn", "text": "Alpha supports beta."}))

    surface = build_proof_surface(state, query="beta")
    context = build_context_payload(state, query="beta")

    assert surface["schema"] == PROOF_SURFACE_SCHEMA
    assert surface["sources"]
    assert surface["excerpts"]
    assert surface["statements"]
    assert context["metadata"]["opaque_summary"] is False
    assert context["items"][0]["atom"]["receipt_ids"]


def test_vm_modules_do_not_add_semantic_regex_policy() -> None:
    for path in (ROOT / "src" / "sensiblaw" / "conversation_vm").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import re" not in text
        assert "from re import" not in text
        assert "regex" not in text.lower()


def test_cli_compile_step_query_roundtrip(tmp_path: Path) -> None:
    turn_path = tmp_path / "turn.json"
    delta_path = tmp_path / "delta.json"
    state_path = tmp_path / "state.json"
    proof_path = tmp_path / "proof.json"
    turn_path.write_text(json.dumps({"turn_id": "cli-turn", "text": "Alpha supports beta."}), encoding="utf-8")

    subprocess.run(
        [sys.executable, "scripts/conversation_vm.py", "compile-turn", "-i", str(turn_path), "-o", str(delta_path)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/conversation_vm.py", "step", "--delta", str(delta_path), "-o", str(state_path)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/conversation_vm.py", "query-surface", "--state", str(state_path), "-q", "beta", "-o", str(proof_path)],
        cwd=ROOT,
        check=True,
    )

    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["schema"] == PROOF_SURFACE_SCHEMA
    assert proof["predicate_atoms"]
