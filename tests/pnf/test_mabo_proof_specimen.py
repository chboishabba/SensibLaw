from __future__ import annotations

from src.pnf.mabo_proof_specimen import (
    LegalChangeKind,
    MultilingualSurface,
    PNFReadingQuestion,
    ProofRole,
    ReadingDepth,
    TranslationLossKind,
    build_flagship_mabo_proof_specimen,
    minimum_adequate_projection,
)


def test_flagship_specimen_keeps_literal_issue_and_proof_roles_distinct() -> None:
    specimen = build_flagship_mabo_proof_specimen()

    assert specimen.literal_formulation != specimen.inferred_issue
    assert [link.role for link in specimen.links] == [
        ProofRole.SUPPORT,
        ProofRole.COMPARATOR,
        ProofRole.RESIDUAL,
    ]
    assert specimen.change_kind is LegalChangeKind.REJECTED
    assert specimen.world_truth_claimed is False
    assert specimen.legal_conclusion_claimed is False


def test_read_projection_hides_internal_density_but_preserves_reopen_handles() -> None:
    specimen = build_flagship_mabo_proof_specimen()
    projection = minimum_adequate_projection(specimen, ReadingDepth.READ)

    assert projection.depth is ReadingDepth.READ
    assert len(projection.visible_nodes) == 5
    assert projection.internal_ids_visible is False
    assert projection.proof_graph_visible is False
    assert all(node.handle.source_ref for node in projection.visible_nodes)
    assert all(node.handle.proof_ref for node in projection.visible_nodes)
    assert projection.hidden_information_discarded is False


def test_pnf_reading_questions_are_role_projections_not_new_grammar_semantics() -> None:
    specimen = build_flagship_mabo_proof_specimen()

    assert specimen.reading_lens.answer_role(PNFReadingQuestion.WHO_DID_IT) == "actor"
    assert specimen.reading_lens.answer_role(PNFReadingQuestion.WHAT_HAPPENED) == "predicate"
    assert specimen.reading_lens.answer_role(PNFReadingQuestion.TO_WHAT) == "patient"
    assert specimen.reading_lens.answer_role(PNFReadingQuestion.HOW_CERTAIN) == "modality"
    assert specimen.reading_lens.role_projection_claims_truth is False


def test_multilingual_qid_identity_does_not_pay_semantic_equivalence() -> None:
    specimen = build_flagship_mabo_proof_specimen()
    surface = MultilingualSurface(
        language="es",
        text="El tribunal rechazó la doctrina.",
        qid="Q185134",
        qid_identity_paid=True,
        semantic_equivalence_paid=False,
        role_carrier_compatible=True,
        translation_losses=(TranslationLossKind.EVIDENTIALITY,),
    )

    aligned = specimen.reading_lens.align_surface(surface)
    assert aligned.qid_identity_paid is True
    assert aligned.semantic_equivalence_paid is False
    assert aligned.role_carrier_compatible is True
    assert aligned.translation_losses == (TranslationLossKind.EVIDENTIALITY,)


def test_wikidata_and_wikipedia_are_navigation_not_legal_authority() -> None:
    specimen = build_flagship_mabo_proof_specimen()
    source = specimen.source_identity

    assert source.wikidata_qid
    assert source.wikipedia_available is True
    assert source.wikidata_identity_is_legal_authority is False
    assert source.wikipedia_is_primary_authority is False
    assert source.full_primary_source_required_for_payment is True
