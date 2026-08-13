from src.storage.postgres.epistemic_factor_report import (
    CanonicalEntityRecord,
    CompositionCandidateRecord,
    EpistemicEntityReport,
    FactorArgument,
    FactorRecord,
    IdentityWitnessRecord,
    render_epistemic_entity_report,
)


def _direct_factor() -> FactorRecord:
    return FactorRecord(
        factor_id=7,
        factor_type="semantic.normative_relation",
        predicate="normative.permission_candidate",
        modal_state=2,
        temporal_state=0,
        document_id=11,
        start_char=100,
        end_char=140,
        epistemic_level=1,
        authority_class=None,
        derivation_id=None,
        arguments=(
            FactorArgument(
                role="bearer",
                surface="reagan",
                source_object_id=17,
            ),
        ),
    )


def test_renderer_distinguishes_surface_from_world_identity() -> None:
    report = EpistemicEntityReport(
        surfaces=("reagan",),
        symbol_ids=(1,),
        direct_object_ids=(17,),
        canonical_entities=(
            CanonicalEntityRecord(
                entity_id=2,
                entity_ref="document-object:abc",
                authority_class="document_derived",
                world_canonical=False,
                canonical_surface="reagan",
            ),
        ),
        witnesses=(),
        direct_factors=(_direct_factor(),),
        derived_factors=(),
        composition_candidates=(),
    )
    rendered = render_epistemic_entity_report(report)
    assert "World-canonical identity proven: **no**" in rendered
    assert "surface identity only" in rendered
    assert "Ronald" not in rendered


def test_renderer_exposes_witnessed_substitution_provenance() -> None:
    derived = FactorRecord(
        factor_id=9,
        factor_type="semantic.legal_transition",
        predicate="legal.commencement_candidate",
        modal_state=0,
        temporal_state=258,
        document_id=11,
        start_char=200,
        end_char=240,
        epistemic_level=3,
        authority_class="document_derived",
        derivation_id=31,
        arguments=(
            FactorArgument(
                role="legal_object",
                surface="he",
                source_object_id=18,
                identity_entity_ref="document-object:abc",
                identity_authority="document_derived",
                identity_witness_ids=(41, 42),
            ),
        ),
    )
    report = EpistemicEntityReport(
        surfaces=("reagan",),
        symbol_ids=(1,),
        direct_object_ids=(17,),
        canonical_entities=(
            CanonicalEntityRecord(
                entity_id=2,
                entity_ref="document-object:abc",
                authority_class="document_derived",
                world_canonical=False,
                canonical_surface="reagan",
            ),
        ),
        witnesses=(
            IdentityWitnessRecord(
                witness_id=41,
                source_object_id=18,
                source_surface="he",
                target_entity_id=2,
                target_entity_ref="document-object:abc",
                witness_kind="anaphor_demand_resolution",
                authority_class="document_derived",
                world_canonical=False,
                demand_id=99,
                candidate_count=1,
                constraint_count=3,
            ),
        ),
        direct_factors=(_direct_factor(),),
        derived_factors=(derived,),
        composition_candidates=(),
    )
    rendered = render_epistemic_entity_report(report)
    assert "D_31 from F_9" in rendered
    assert "surface=he" in rendered
    assert "witnesses=41,42" in rendered
    assert "Original factor remains unchanged" in rendered


def test_composition_candidate_is_not_described_as_a_proposition() -> None:
    report = EpistemicEntityReport(
        surfaces=("example",),
        symbol_ids=(1,),
        direct_object_ids=(17,),
        canonical_entities=(),
        witnesses=(),
        direct_factors=(_direct_factor(),),
        derived_factors=(),
        composition_candidates=(
            CompositionCandidateRecord(
                candidate_id=5,
                left_factor_id=7,
                right_factor_id=8,
                left_role="bearer",
                right_role="subject",
                bridge_surface="reagan",
                bridge_entity_ref=None,
                identity_authority=None,
                candidate_rank=0,
            ),
        ),
    )
    rendered = render_epistemic_entity_report(report)
    assert "**structural candidates only**" in rendered
    assert "do not themselves license a semantic conclusion" in rendered
    assert "C_5: F_7" in rendered
