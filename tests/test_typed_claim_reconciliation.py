from __future__ import annotations

from src.fact_intake import (
    AFFIDAVIT_RELATION_TYPES,
    normalize_object_type_claim,
    normalize_proposition,
    normalize_response_unit,
    normalize_wikidata_claim_row,
    reduce_typed_relation,
)


def test_walked_dog_denial_reduces_to_explicit_dispute_without_promotion() -> None:
    proposition = normalize_proposition(
        subject="Alex",
        predicate="walked",
        object="the dog",
        text="Alex walked the dog",
    )
    response = normalize_response_unit(
        subject="Alex",
        predicate="walked",
        object="the dog",
        polarity="negative",
        text="Alex did not walk the dog",
        response_role="dispute",
    )

    relation = reduce_typed_relation(proposition, response)

    assert relation["relation_type"] == "explicit_dispute"
    assert relation["relation_root"] == "invalidates"
    assert relation["bucket"] == "disputed"
    assert relation["promotion_state"]["promoted"] is False


def test_walked_dog_same_claim_supports_without_proof_promotion() -> None:
    proposition = normalize_proposition(
        subject="Alex",
        predicate="walked",
        object="the dog",
        text="Alex walked the dog",
    )
    response = normalize_response_unit(
        subject="Alex",
        predicate="walked",
        object="the dog",
        text="Alex walked the dog",
    )

    relation = reduce_typed_relation(proposition, response)

    assert relation["relation_type"] == "exact_support"
    assert relation["relation_root"] == "supports"
    assert relation["bucket"] == "supported"
    assert relation["promotion_state"]["promoted"] is False


def test_adjacent_and_procedural_examples_do_not_reduce_to_support() -> None:
    proposition = normalize_proposition(
        subject="Alex",
        predicate="walked",
        object="the dog",
        text="Alex walked the dog",
    )
    adjacent = normalize_response_unit(
        subject="Alex",
        predicate="fed",
        object="the dog",
        text="Alex fed the dog earlier",
    )
    procedural = normalize_response_unit(
        text="I will address this after the documents are produced.",
        response_role="procedural_frame",
    )

    adjacent_relation = reduce_typed_relation(
        proposition,
        adjacent,
        relation_hint="adjacent_event",
    )
    procedural_relation = reduce_typed_relation(proposition, procedural)

    assert adjacent_relation["relation_type"] == "adjacent_event"
    assert adjacent_relation["relation_root"] == "non_resolving"
    assert adjacent_relation["relation_derivation"] == "caller_hint"
    assert procedural_relation["relation_type"] == "procedural_nonanswer"
    assert procedural_relation["relation_root"] == "non_resolving"
    assert procedural_relation["relation_derivation"] == "derived"


def test_object_type_claims_normalize_four_positive_claims() -> None:
    claims = [
        normalize_object_type_claim(subject="6", claimed_type="1-morphism"),
        normalize_object_type_claim(subject="6", claimed_type="2-morphism"),
        normalize_object_type_claim(subject="6", claimed_type="j-invariant"),
        normalize_object_type_claim(subject="6", claimed_type="dolphin"),
    ]

    assert [claim["claimed_type"] for claim in claims] == [
        "1-morphism",
        "2-morphism",
        "j-invariant",
        "dolphin",
    ]
    assert {claim["polarity"] for claim in claims} == {"positive"}
    assert {claim["kind"] for claim in claims} == {"object_type_claim"}
    assert {claim["witness_status"] for claim in claims} == {"typing_context_missing"}
    assert {claim["review_status"] for claim in claims} == {"witness_pending"}
    assert all(claim["promotion_state"]["promoted"] is False for claim in claims)


def test_object_type_claim_with_context_and_rule_materializes_witness_status() -> None:
    claim = normalize_object_type_claim(
        subject="6",
        claimed_type="1-morphism",
        context={"bicategory": "demo-bicat"},
        witness_metadata={"typing_rule": "demo-source-target-composition-rule"},
    )

    assert claim["witness_status"] == "typing_witnessed"
    assert claim["review_status"] == "reviewed_carrier"
    assert claim["promotion_state"]["promoted"] is False


def test_different_positive_object_types_do_not_contradict_without_exclusion_witness() -> None:
    one_morphism = normalize_object_type_claim(subject="6", claimed_type="1-morphism")
    dolphin = normalize_object_type_claim(subject="6", claimed_type="dolphin")

    relation = reduce_typed_relation(one_morphism, dolphin)

    assert relation["relation_type"] == "adjacent_event"
    assert relation["relation_root"] == "non_resolving"
    assert relation["bucket"] == "adjacent_event"
    assert relation["promotion_state"]["promoted"] is False


def test_same_subject_same_type_opposite_polarity_is_object_type_dispute() -> None:
    dolphin = normalize_object_type_claim(subject="6", claimed_type="dolphin")
    not_dolphin = normalize_object_type_claim(
        subject="6",
        claimed_type="dolphin",
        polarity="negative",
    )

    relation = reduce_typed_relation(dolphin, not_dolphin)

    assert relation["relation_type"] == "explicit_dispute"
    assert relation["relation_root"] == "invalidates"
    assert relation["bucket"] == "disputed"


def test_wikidata_claim_row_preserves_claim_bundle_and_provenance() -> None:
    row = normalize_wikidata_claim_row(
        subject="Q42",
        property="P31",
        value="Q5",
        qualifiers={"P580": "1952-03-11"},
        references=[{"stated_in": "Q5375741", "reference_url": "https://example.test/ref"}],
        rank="normal",
    )

    assert row["kind"] == "wikidata_claim_row"
    assert row["subject"] == "Q42"
    assert row["property"] == "P31"
    assert row["value"] == "Q5"
    assert row["qualifiers"] == {"P580": "1952-03-11"}
    assert row["references"][0]["stated_in"] == "Q5375741"
    assert row["evidence_state"] == "observed"
    assert row["promotion_state"]["promoted"] is False
    assert row["truth_claimed"] is False
    assert row["truth_claimed_is_false"] is True
    assert row["live_edit_authority"] is False
    assert row["live_edit_authority_is_false"] is True


def test_wikidata_deprecated_rank_is_review_metadata_not_contradiction_or_promotion() -> None:
    row = normalize_wikidata_claim_row(
        subject="Q42",
        property="P31",
        value="Q55983715",
        rank="deprecated",
    )

    assert row["rank"] == "deprecated"
    assert row["operational_status"] == "deprecated"
    assert row["evidence_state"] == "held_for_review"
    assert row["promotion_state"]["promoted"] is False
    assert row["truth_claimed"] is False
    assert row["live_edit_authority"] is False


def test_wikidata_preferred_and_normal_rank_do_not_become_truth_or_proof() -> None:
    preferred = normalize_wikidata_claim_row(
        subject="Q42",
        property="P31",
        value="Q5",
        rank="preferred",
    )
    normal = normalize_wikidata_claim_row(
        subject="Q42",
        property="P31",
        value="Q5",
        rank="normal",
    )

    assert preferred["rank"] == "preferred"
    assert normal["rank"] == "normal"
    assert preferred["evidence_state"] == "observed"
    assert normal["evidence_state"] == "observed"
    assert preferred["promotion_state"]["promoted"] is False
    assert normal["promotion_state"]["promoted"] is False
    assert preferred["truth_claimed"] is False
    assert normal["truth_claimed"] is False
    assert preferred["live_edit_authority"] is False
    assert normal["live_edit_authority"] is False


def test_affidavit_relation_vocabulary_remains_canonical() -> None:
    assert AFFIDAVIT_RELATION_TYPES == (
        "exact_support",
        "equivalent_support",
        "explicit_dispute",
        "implicit_dispute",
        "partial_overlap",
        "adjacent_event",
        "substitution",
        "procedural_nonanswer",
        "unrelated",
    )
