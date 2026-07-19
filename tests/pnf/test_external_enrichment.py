from __future__ import annotations

from src.ontology.external_enrichment import (
    ExternalCandidate,
    ExternalLookupDemand,
    build_external_candidate_set,
    group_lookup_demands,
)
from src.pnf.external_enrichment_projection import project_external_lookup_demands


def _qid_candidate() -> ExternalCandidate:
    return ExternalCandidate(
        provider_ref="wikidata-wbsearchentities:v0_1",
        external_id="Q30",
        label="United States of America",
        aliases=("United States", "the United States", "U.S.", "America"),
        candidate_kind="wikidata_item",
        source_url="https://www.wikidata.org/wiki/Q30",
    )


def test_alias_surfaces_can_share_qid_candidate_without_identity_closure() -> None:
    candidate = _qid_candidate()
    sets = []
    for index, surface in enumerate(("the United States", "U.S.", "America")):
        demand = ExternalLookupDemand(
            demand_ref=f"demand:{index}",
            subject_ref=f"factor:{index}",
            surface=surface,
        )
        candidate_set, pressure = build_external_candidate_set(
            demand,
            provider_ref=candidate.provider_ref,
            candidates=(candidate,),
        )
        sets.append(candidate_set)
        assert candidate_set.candidates[0].external_id == "Q30"
        assert candidate_set.to_dict()["identity_closed"] is False
        assert "external_identity_unresolved" in candidate_set.residuals
        assert pressure.after.lookup_absence == 0.0
        assert pressure.after.external_identity_unresolved == 1.0
        assert pressure.to_dict()["demand_closed"] is False

    assert len({row.candidate_set_ref for row in sets}) == 3
    assert len({row.candidates[0].candidate_ref for row in sets}) == 1


def test_linguistic_types_do_not_false_conflict_with_wikidata_qid_types() -> None:
    demand = ExternalLookupDemand(
        demand_ref="demand:usa",
        subject_ref="factor:usa",
        surface="United States",
        local_type_refs=("named_entity_candidate", "semantic-family:entity"),
    )
    candidate = ExternalCandidate(
        provider_ref="wikidata-wbsearchentities:v0_1",
        external_id="Q30",
        label="United States",
        candidate_kind="wikidata_item",
        type_refs=("Q6256",),
    )

    candidate_set, _pressure = build_external_candidate_set(
        demand,
        provider_ref=candidate.provider_ref,
        candidates=(candidate,),
    )

    assessment = candidate_set.assessments[0]
    assert assessment.type_score == 0.5
    assert assessment.compatibility_state == "compatible_candidate"
    assert "type_evidence_incomplete" in assessment.reasons
    assert "external_candidate_type_mismatch" not in candidate_set.residuals


def test_pressure_monotonicity_uses_the_complete_vector() -> None:
    demand = ExternalLookupDemand(
        demand_ref="demand:bush",
        subject_ref="factor:bush",
        surface="Bush",
    )
    candidates = tuple(
        ExternalCandidate(
            provider_ref="wikidata-wbsearchentities:v0_1",
            external_id=f"Q{index}",
            label=f"Bush candidate {index}",
            aliases=("Bush",),
            candidate_kind="wikidata_item",
        )
        for index in range(1, 4)
    )

    candidate_set, pressure = build_external_candidate_set(
        demand,
        provider_ref="wikidata-wbsearchentities:v0_1",
        candidates=candidates,
    )

    assert "external_candidate_ambiguity" in candidate_set.residuals
    assert pressure.after.lookup_absence == 0.0
    assert pressure.after.candidate_ambiguity > 1.0
    assert pressure.after.total > pressure.before.total
    assert pressure.monotone is False


def test_lookup_grouping_deduplicates_same_semantic_request_only() -> None:
    rows = (
        ExternalLookupDemand("demand:a", "factor:a", "George W. Bush"),
        ExternalLookupDemand("demand:b", "factor:b", "  george w. bush  "),
        ExternalLookupDemand("demand:c", "factor:c", "Bush"),
    )
    grouped = group_lookup_demands(rows)

    assert len(grouped) == 2
    assert sorted(len(group) for _key, group in grouped) == [1, 2]


def test_projector_selects_external_named_mentions_but_not_pronouns() -> None:
    artifacts = {
        "licensing": {
            "mentions": [
                {
                    "mention_ref": "mention:usa",
                    "canonical_surface": "the United States",
                    "generation_reason": "named_entity_shape",
                },
                {
                    "mention_ref": "mention:he",
                    "canonical_surface": "He",
                    "generation_reason": "grammar_phrase",
                },
            ]
        },
        "refined_pnf_graph": {
            "factors": [
                {
                    "factor_ref": "factor:usa",
                    "factor_type": "semantic.mention_identity",
                    "metadata": {"mention_ref": "mention:usa"},
                    "alternatives": [
                        {
                            "type_ref": "named_entity_candidate",
                            "value": {
                                "mention_ref": "mention:usa",
                                "semantic_family": "entity",
                                "local_type": "named_entity_candidate",
                            },
                        }
                    ],
                },
                {
                    "factor_ref": "factor:he",
                    "factor_type": "semantic.mention_identity",
                    "metadata": {"mention_ref": "mention:he"},
                    "alternatives": [
                        {
                            "type_ref": "pronominal_argument",
                            "value": {
                                "mention_ref": "mention:he",
                                "semantic_family": "entity",
                                "local_type": "pronoun_realisation",
                            },
                        }
                    ],
                },
            ]
        },
        "resolution_demands": [
            {
                "demand_ref": "demand:usa",
                "factor_ref": "factor:usa",
                "budget": "bounded_external_evidence",
                "requested_facets": ["external_identity_unresolved"],
            },
            {
                "demand_ref": "demand:he",
                "factor_ref": "factor:he",
                "budget": "bounded_external_evidence",
                "requested_facets": ["external_identity_unresolved"],
            },
        ],
    }

    demands = project_external_lookup_demands(artifacts)

    assert [row.surface for row in demands] == ["the United States"]
    assert demands[0].demand_kind == "entity_identity"
    assert demands[0].subject_ref == "factor:usa"
