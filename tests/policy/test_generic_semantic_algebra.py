from __future__ import annotations

import pytest

from src.ingestion.media_adapter_contract import MediaAdapterCapability
from src.ingestion.media_refs import SegmentRef, TextSpanRef
from src.language import (
    AnnotationGraph,
    AnnotationLayer,
    ReductionGrammar,
    SpanAnnotation,
    apply_reduction_grammar,
)
from src.pnf import ClosureContract, PNFGraph, assess_pnf_closure, derive_resolution_demands
from src.policy.algebra import (
    Factor,
    FactorRefinement,
    MeetState,
    TypedAlternative,
    TypedMeet,
)
from src.policy.carriers import canonical_sha256
from src.resolution import ExternalSnapshotEnvelope, reconcile_meets


def alternative(ref: str, value: object) -> TypedAlternative:
    return TypedAlternative(
        alternative_ref=ref,
        value=value,
        type_ref="type:test",
        derivation_refs=("grammar:test",),
    )


def test_factor_serialization_is_deterministic_not_semantic_order() -> None:
    factor = Factor(
        factor_ref="factor:test",
        factor_type="pnf.subject",
        alternatives=(alternative("z", "Bush"), alternative("a", "the president")),
    )
    assert [row["alternative_ref"] for row in factor.to_dict()["alternatives"]] == [
        "a",
        "z",
    ]
    assert {row["value"] for row in factor.to_dict()["alternatives"]} == {
        "Bush",
        "the president",
    }


def test_factor_operations_preserve_immutability() -> None:
    prior = Factor(
        factor_ref="factor:event",
        factor_type="pnf.eventuality",
        alternatives=(alternative("date", "September 11"),),
        residuals=("event_identity_unresolved",),
    )
    resulting = prior.add_alternatives(
        alternative("event", "September 11 attacks")
    ).transition_residuals(
        remove=("event_identity_unresolved",), closure_state="closed"
    )
    assert [row.alternative_ref for row in prior.alternatives] == ["date"]
    assert {row.alternative_ref for row in resulting.alternatives} == {"date", "event"}
    assert resulting.residuals == ()


def test_factor_refinement_cannot_change_factor_identity() -> None:
    with pytest.raises(ValueError):
        FactorRefinement(
            refinement_ref="refinement:bad",
            prior_factor=Factor("factor:a", "pnf.subject"),
            resulting_factor=Factor("factor:b", "pnf.subject"),
        ).to_dict()


def test_typed_meet_product_derives_structural_outcome() -> None:
    assessment = reconcile_meets(
        assessment_ref="assessment:event",
        subject_ref="event:local",
        meets=(
            TypedMeet(
                meet_ref="meet:time",
                left_ref="event:local",
                right_ref="wm:event",
                meet_type="temporal_interval_meet",
                state=MeetState.COMPATIBLE,
            ),
            TypedMeet(
                meet_ref="meet:lineage",
                left_ref="event:local",
                right_ref="wm:event",
                meet_type="lineage_meet",
                state=MeetState.COMPATIBLE_WITH_REFINEMENT,
                residual_refs=("source_lineage_unresolved",),
            ),
        ),
    )
    assert assessment.outcome == "compatible_with_refinement"
    assert assessment.residual_refs == ("source_lineage_unresolved",)


def test_annotation_reduction_is_branch_preserving() -> None:
    layer = AnnotationLayer(
        layer_ref="layer:shared",
        tokenizer_ref="spacy:test",
        text_sha256="abc",
        span_annotations=(
            SpanAnnotation("span:date", 0, 2, "calendar_expression", "September 11"),
            SpanAnnotation("span:title", 0, 2, "title_shape", "September Eleven"),
        ),
    )
    result = apply_reduction_grammar(
        graph=AnnotationGraph("graph:text", (layer,)),
        grammar=ReductionGrammar(
            grammar_ref="grammar:temporal-or-title",
            required_span_types=("calendar_expression", "title_shape"),
            output_factor_type="pnf.temporal_context",
            output_type_ref="semantic.form",
        ),
        factor_ref="factor:temporal-context",
    )
    assert result.matched is True
    assert len(result.factor.alternatives) == 2


def test_pnf_graph_refines_one_factor_and_demands_open_factor() -> None:
    subject = Factor("factor:subject", "pnf.subject", closure_state="closed")
    event = Factor(
        "factor:event",
        "pnf.eventuality",
        residuals=("external_identity",),
        closure_state="requires_external_resolution",
    )
    graph = PNFGraph("pnf:gwb", "document:gwb", (subject, event))
    demands = derive_resolution_demands(graph)
    assert [row["factor_ref"] for row in demands] == ["factor:event"]
    refined_event = event.transition_residuals(
        remove=("external_identity",), closure_state="closed"
    )
    refined = graph.replace_factor(refined_event)
    assert refined.factor("factor:subject") is subject
    assert refined.factor("factor:event").closure_state == "closed"


def test_closure_contract_keeps_pressure_semantics_separate() -> None:
    graph = PNFGraph(
        "pnf:test",
        "document:test",
        (Factor("factor:subject", "pnf.subject", residuals=("type_missing",)),),
    )
    pressures = assess_pnf_closure(
        graph,
        ClosureContract("contract:test", ("pnf.subject", "pnf.object")),
    )
    assert {row.pressure_kind.value for row in pressures} == {"closure"}
    assert {row.state for row in pressures} == {"open", "missing_factor"}


def test_snapshot_envelope_preserves_backend_specific_payload() -> None:
    envelope = ExternalSnapshotEnvelope(
        snapshot_ref="worldmonitor:event:1@v1",
        backend_ref="worldmonitor",
        external_ref="event:1",
        version_ref="v1",
        formal_role="observation",
        payload={"observed_at": "2026-07-18", "agency": "source-a"},
        provenance_refs=("worldmonitor:snapshot:v1",),
    ).to_dict()
    assert envelope["formal_role"] == "observation"
    assert envelope["payload"]["agency"] == "source-a"
    assert envelope["payload_sha256"] == canonical_sha256(envelope["payload"])


def test_media_contract_is_capability_not_corpus_specific() -> None:
    capability = MediaAdapterCapability(
        adapter_ref="media:pdf",
        media_types=("application/pdf",),
    ).to_dict()
    assert capability["adapter_ref"] == "media:pdf"
    assert "gwb" not in str(capability).lower()
    assert "au" not in str(capability).lower()
    assert TextSpanRef("text:1", 0, 3).to_dict()["end_char"] == 3
    assert SegmentRef("text:1", "segment:1", 0, page=1).to_dict()["page"] == 1
