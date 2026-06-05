from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.media_adapter import CanonicalUnit
from src.sensiblaw.interfaces import (
    collect_canonical_lexeme_terms,
    collect_canonical_predicate_atoms,
    collect_canonical_predicate_atoms_from_units,
    collect_canonical_predicate_pnfs,
    collect_canonical_predicate_pnfs_from_units,
    collect_canonical_relational_bundle,
    collect_canonical_structural_ir_feed,
    collect_canonical_structural_ir_feed_from_units,
)
import src.sensiblaw.interfaces.shared_reducer as shared_reducer
from src.text import LATENT_FIBRE_INDEX_SCHEMA


def test_collect_canonical_predicate_atoms_projects_predicate_relations() -> None:
    atoms = collect_canonical_predicate_atoms("Leader publishes transactions.")

    assert atoms
    projected = atoms[0]
    assert projected.predicate == "publish"
    assert projected.structural_signature == "utterance_event:publish"
    assert projected.roles["subject"].value == "leader"
    assert projected.roles["action"].value == "publish"
    assert projected.roles["object"].value == "transactions"
    assert projected.roles["object"].status == "bound"
    assert projected.qualifiers.polarity == "positive"
    assert projected.wrapper.evidence_only is True
    assert projected.atom_id is not None
    assert projected.provenance
    assert "head_modifiers" not in projected.modifiers


def test_collect_canonical_relational_bundle_falls_back_without_spacy(monkeypatch) -> None:
    def missing_spacy(_text: str):
        raise ModuleNotFoundError("spacy")

    monkeypatch.setattr(shared_reducer, "parse_with_spacy", missing_spacy)

    bundle = collect_canonical_relational_bundle("Leader publishes transactions.")
    atom_text_by_id = {atom["id"]: atom["text"].casefold() for atom in bundle["atoms"]}
    predicate_pairs = [
        tuple(atom_text_by_id[role["atom"]] for role in relation["roles"] if role.get("atom"))
        for relation in bundle["relations"]
        if relation["type"] == "predicate"
    ]

    assert any("publishes" in pair and "transactions" in pair for pair in predicate_pairs)


def test_collect_canonical_predicate_atoms_is_empty_when_no_predicate_relation_exists() -> None:
    atoms = collect_canonical_predicate_atoms("Bitcoin?")

    assert atoms == []


def test_collect_canonical_lexeme_terms_is_stable_and_unique() -> None:
    terms = collect_canonical_lexeme_terms("BTC price, BTC price today")

    assert terms == ("btc", "price", "today")


def test_collect_canonical_structural_ir_feed_emits_bounded_artifact_family() -> None:
    feed = collect_canonical_structural_ir_feed("Leader publishes transactions?")

    assert feed["source"] == "sensiblaw_shared_reducer"
    assert feed["predicate_atoms"]
    assert feed["signal_atoms"]
    assert feed["provenance_refs"]
    assert feed["constraint_receipt"]["canonical_mode"] == "deterministic_legal"
    assert feed["constraint_receipt"]["question_mode"] is True
    assert feed["constraint_receipt"]["evidence_only"] is True
    assert isinstance(feed["constraint_receipt"]["tokenizer_profile_id"], str)
    first_signal = feed["signal_atoms"][0]
    assert "kind" in first_signal
    assert "norm_text" in first_signal
    assert "provenance_ref" in first_signal
    first_predicate = feed["predicate_atoms"][0]
    assert first_predicate["structural_signature"] == "utterance_event:publish"
    assert first_predicate["roles"]["subject"]["value"] == "leader"
    assert first_predicate["roles"]["action"]["value"] == "publish"
    assert first_predicate["roles"]["object"]["value"] == "transactions"
    assert first_predicate["qualifiers"]["polarity"] == "positive"
    assert first_predicate["wrapper"]["evidence_only"] is True


def test_collect_canonical_structural_ir_feed_does_not_emit_semantic_route_or_intent_keys() -> None:
    feed = collect_canonical_structural_ir_feed("Leader publishes transactions.")

    forbidden = {"intent", "route", "asset", "advice", "interaction_mode"}

    def walk(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                assert str(key) not in forbidden
                walk(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                walk(nested)

    walk(feed)


def test_collect_canonical_predicate_atoms_from_units_requires_body_qualified_units() -> None:
    units = (
        CanonicalUnit(
            unit_id="u:0",
            segment_id="s:0",
            unit_kind="text_run",
            text="jade.io",
            start_char=0,
            end_char=7,
            metadata={"body_qualified": False},
        ),
        CanonicalUnit(
            unit_id="u:1",
            segment_id="s:1",
            unit_kind="text_run",
            text="Leader publishes transactions.",
            start_char=8,
            end_char=39,
            metadata={"body_qualified": True},
        ),
    )

    atoms = collect_canonical_predicate_atoms_from_units(units)

    assert atoms
    assert all(atom.predicate != "jade.io" for atom in atoms)
    assert atoms[0].predicate == "publish"


def test_collect_canonical_predicate_pnfs_exposes_real_pnf_carrier() -> None:
    pnfs = collect_canonical_predicate_pnfs("Leader publishes transactions.")

    assert pnfs
    first = pnfs[0]
    assert first.structural_signature == "utterance_event:publish"
    assert first.roles["subject"].value == "leader"
    assert first.roles["action"].value == "publish"
    assert first.roles["object"].value == "transactions"
    assert first.qualifiers.polarity == "positive"
    assert first.wrapper.evidence_only is True


def test_collect_canonical_predicate_pnfs_from_units_requires_body_qualified_units() -> None:
    units = (
        CanonicalUnit(
            unit_id="u:0",
            segment_id="s:0",
            unit_kind="text_run",
            text="jade.io",
            start_char=0,
            end_char=7,
            metadata={"body_qualified": False},
        ),
        CanonicalUnit(
            unit_id="u:1",
            segment_id="s:1",
            unit_kind="text_run",
            text="Leader publishes transactions.",
            start_char=8,
            end_char=39,
            metadata={"body_qualified": True},
        ),
    )

    pnfs = collect_canonical_predicate_pnfs_from_units(units)

    assert len(pnfs) == 1
    assert pnfs[0].roles["object"].value == "transactions"


def test_collect_canonical_predicate_atoms_emits_utterance_support_sign_carriers() -> None:
    positive = collect_canonical_predicate_atoms("I walked the dog.")
    negative = collect_canonical_predicate_atoms("I did not walk the dog.")

    assert positive and negative
    left = positive[0]
    right = negative[0]
    assert left.predicate == "walk"
    assert right.predicate == "walk"
    assert left.structural_signature == "utterance_event:walk"
    assert right.structural_signature == "utterance_event:walk"
    assert left.roles["subject"].value == right.roles["subject"].value == "i"
    assert left.roles["object"].value == right.roles["object"].value == "dog"
    assert left.qualifiers.polarity == "positive"
    assert right.qualifiers.polarity == "negative"
    assert "negation_evidence" in right.modifiers


def test_collect_canonical_predicate_atoms_emits_copular_reclassification_pair() -> None:
    atoms = [
        atom
        for atom in collect_canonical_predicate_atoms(
            "6 is a 1-morphism, not an object.",
            enable_utterance_latent_fibres=False,
        )
        if atom.predicate == "be/classify"
    ]

    assert len(atoms) == 2
    by_theme = {atom.roles["theme"].value: atom for atom in atoms}
    assert by_theme["1-morphism"].roles["agent"].value == "6"
    assert by_theme["1-morphism"].qualifiers.polarity == "positive"
    assert by_theme["object"].qualifiers.polarity == "negative"
    assert by_theme["object"].structural_signature == "classification:agent-theme"
    assert by_theme["object"].wrapper.status == "directEvidence"


def test_collect_canonical_predicate_atoms_emits_not_a_it_is_b_pair() -> None:
    atoms = [
        atom
        for atom in collect_canonical_predicate_atoms(
            "x isn't A, it's B.",
            enable_utterance_latent_fibres=False,
        )
        if atom.predicate == "be/classify"
    ]

    assert {(atom.roles["theme"].value, atom.qualifiers.polarity) for atom in atoms} == {
        ("a", "negative"),
        ("b", "positive"),
    }


def test_collect_canonical_structural_ir_feed_enriches_predicate_atoms_from_env_seeded_latent_fibre_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_path = _latent_fibre_artifact(tmp_path)
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH", str(artifact_path))

    feed = collect_canonical_structural_ir_feed("I walked the dog.")

    assert feed["predicate_atoms"]
    atom = feed["predicate_atoms"][0]
    assert atom["semantic_comparison_mode"] == "latent_candidate"
    assert atom["support_fibres"]
    assert atom["latent_grounding"]["artifact_id"] == "fixture-local-corpus-v1"


def test_collect_canonical_structural_ir_feed_from_units_skips_non_body_units() -> None:
    units = (
        CanonicalUnit(
            unit_id="u:0",
            segment_id="s:0",
            unit_kind="text_run",
            text="View this document in a browser",
            start_char=0,
            end_char=31,
            metadata={"body_qualified": False},
        ),
    )

    feed = collect_canonical_structural_ir_feed_from_units(units)

    assert feed["predicate_atoms"] == []
    assert feed["signal_atoms"] == []
    assert feed["provenance_refs"] == []
    assert feed["constraint_receipt"]["evidence_only"] is True


def test_collect_canonical_relational_bundle_emits_batch_progress() -> None:
    events: list[tuple[str, dict]] = []
    text = "Leader publishes transactions. Verifier checks signatures. Time orders events."

    bundle = collect_canonical_relational_bundle(
        text,
        progress_callback=lambda stage, details: events.append((stage, details)),
    )

    assert bundle["relations"]
    assert events
    progress_events = [details for stage, details in events if stage == "relational_bundle_progress"]
    assert progress_events
    last = progress_events[-1]
    assert last["sentences_done"] == last["total_sentences"]
    assert last["words_done"] == last["total_words"]
    assert last["relation_count"] >= 1


def test_collect_canonical_structural_ir_feed_emits_feed_progress() -> None:
    events: list[tuple[str, dict]] = []

    feed = collect_canonical_structural_ir_feed(
        "Leader publishes transactions. Verifier checks signatures. Time orders events.",
        progress_callback=lambda stage, details: events.append((stage, details)),
    )

    assert feed["predicate_atoms"]
    progress_events = [details for stage, details in events if stage == "structural_feed_progress"]
    assert progress_events
    assert any(details["stage"] == "relational_bundle_progress" for details in progress_events)
    final = progress_events[-1]
    assert final["stage"] == "receipt_finalize"
    assert final["provenance_ref_count"] == len(feed["provenance_refs"])


def _latent_fibre_artifact(path: Path) -> Path:
    artifact = {
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
        "predicate_nodes": {
            "walk": {"observation_count": 4},
        },
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
    artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
    return artifact_path


def _latent_fibre_artifact_with_id(
    path: Path,
    *,
    artifact_id: str,
    support_target: str = "amble",
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    artifact = {
        "artifact_id": artifact_id,
        "schema_version": LATENT_FIBRE_INDEX_SCHEMA,
        "source_corpus": {
            "manifest_id": "fixture-corpus",
            "manifest_hash": f"sha256:{artifact_id}",
        },
        "extraction_profile": {
            "name": "fixture-pnf-cooccurrence",
            "version": "v1",
        },
        "model_assets": [],
        "predicate_nodes": {
            "walk": {"observation_count": 4},
        },
        "role_context_signatures": {},
        "derived_fibre_candidates": [
            {
                "candidate_id": f"fibre:walk-{support_target}:canonical",
                "source_predicate": "walk",
                "target_predicate": support_target,
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
    artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
    return artifact_path


def test_collect_canonical_predicate_atoms_can_enrich_from_utterance_latent_fibre_index(tmp_path: Path) -> None:
    artifact_path = _latent_fibre_artifact(tmp_path)

    atoms = collect_canonical_predicate_atoms(
        "I walked the dog.",
        utterance_latent_fibre_index=artifact_path,
    )

    assert atoms
    atom = atoms[0]
    assert atom.semantic_comparison_mode == "latent_candidate"
    assert atom.support_fibres
    assert atom.support_fibres[0]["candidate_id"] == "fibre:walk-amble:canonical"
    assert atom.latent_grounding["artifact_id"] == "fixture-local-corpus-v1"


def test_collect_canonical_predicate_atoms_falls_back_if_latent_fibre_index_unavailable(tmp_path: Path) -> None:
    atoms = collect_canonical_predicate_atoms(
        "I walked the dog.",
        utterance_latent_fibre_index=tmp_path / "missing-latent-fibre.json",
    )

    assert atoms
    atom = atoms[0]
    assert atom.support_fibres == ()
    assert not atom.latent_grounding


def test_collect_canonical_predicate_atoms_can_disable_default_latent_fibre_index(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRES_DISABLED", "1")

    atoms = collect_canonical_predicate_atoms("I walked the dog.")

    assert atoms
    atom = atoms[0]
    assert atom.support_fibres == ()
    assert not atom.latent_grounding
    assert atom.semantic_comparison_mode == "exact"


def test_collect_canonical_predicate_atoms_marks_unsupported_default_fibre_as_abstained() -> None:
    atoms = collect_canonical_predicate_atoms("Leader publishes transactions.")

    assert atoms
    atom = atoms[0]
    assert atom.predicate == "publish"
    assert atom.support_fibres == ()
    assert atom.semantic_comparison_mode == "abstained"
    assert atom.latent_grounding["artifact_id"] == "sensiblaw-utterance-latent-fibres-v0_1"
    assert atom.latent_grounding["abstention_reason"] == "no_supported_latent_fibre"


def test_collect_canonical_predicate_atoms_uses_env_seeded_latent_fibre_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_path = _latent_fibre_artifact(tmp_path)
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH", str(artifact_path))

    atoms = collect_canonical_predicate_atoms("I walked the dog.")

    assert atoms
    atom = atoms[0]
    assert atom.semantic_comparison_mode == "latent_candidate"
    assert atom.support_fibres
    assert atom.latent_grounding["artifact_id"] == "fixture-local-corpus-v1"


def test_collect_canonical_predicate_atoms_resolves_utterance_latent_fibre_index_by_precedence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    explicit_path = _latent_fibre_artifact_with_id(tmp_path / "explicit", artifact_id="explicit-index")
    env_path = _latent_fibre_artifact_with_id(tmp_path / "env", artifact_id="env-index")
    config_path = _latent_fibre_artifact_with_id(tmp_path / "config", artifact_id="config-index")
    legacy_path = _latent_fibre_artifact_with_id(tmp_path / "legacy", artifact_id="legacy-index")
    config = {
        "utterance_latent_fibres": {
            "utterance_latent_fibre_index_path": str(config_path),
        }
    }
    config_path_spec = tmp_path / "latent-config.json"
    config_path_spec.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")

    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH", str(env_path))
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX", str(legacy_path))
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG", str(config_path_spec))

    shared_reducer._clear_utterance_latent_fibre_index_cache()
    atoms = collect_canonical_predicate_atoms(
        "I walked the dog.",
        utterance_latent_fibre_index=explicit_path,
    )
    assert atoms
    assert atoms[0].latent_grounding["artifact_id"] == "explicit-index"

    shared_reducer._clear_utterance_latent_fibre_index_cache()
    atoms = collect_canonical_predicate_atoms("I walked the dog.")
    assert atoms
    assert atoms[0].latent_grounding["artifact_id"] == "env-index"

    shared_reducer._clear_utterance_latent_fibre_index_cache()
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH", "")
    atoms = collect_canonical_predicate_atoms("I walked the dog.")
    assert atoms
    assert atoms[0].latent_grounding["artifact_id"] == "config-index"

    shared_reducer._clear_utterance_latent_fibre_index_cache()
    monkeypatch.setenv("SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG", "")
    atoms = collect_canonical_predicate_atoms("I walked the dog.")
    assert atoms
    assert atoms[0].latent_grounding["artifact_id"] == "legacy-index"
