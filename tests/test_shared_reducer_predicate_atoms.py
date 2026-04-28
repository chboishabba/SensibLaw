from __future__ import annotations

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


def test_collect_canonical_predicate_atoms_projects_predicate_relations() -> None:
    atoms = collect_canonical_predicate_atoms("Leader publishes transactions.")

    assert atoms
    projected = atoms[0]
    assert projected.predicate == "publishes"
    assert projected.structural_signature == "publishes"
    assert projected.roles["argument"].value == "transactions"
    assert projected.roles["argument"].status == "bound"
    assert projected.qualifiers.polarity == "positive"
    assert projected.wrapper.evidence_only is True
    assert projected.atom_id is not None
    assert projected.provenance
    assert "head_modifiers" not in projected.modifiers


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
    assert first_predicate["structural_signature"] == "publishes"
    assert first_predicate["roles"]["argument"]["value"] == "transactions"
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
    assert atoms[0].predicate == "publishes"


def test_collect_canonical_predicate_pnfs_exposes_real_pnf_carrier() -> None:
    pnfs = collect_canonical_predicate_pnfs("Leader publishes transactions.")

    assert pnfs
    first = pnfs[0]
    assert first.structural_signature == "publishes"
    assert first.roles["argument"].value == "transactions"
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
    assert pnfs[0].roles["argument"].value == "transactions"


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
