"""Pairwise-free PostgreSQL operational document compilation.

The compatibility compiler retains its expanded JSON carrier. This module is
the active PostgreSQL path: it shares the same parser, annotation graph,
reductions, constraints, role refinement and demand machinery, but never
materializes pairwise binding evidence or per-candidate factor alternatives.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from src.pnf.operational_reference_binding import (
    build_operational_reference_binding_artifacts,
)
from src.policy import corpus_compilation as legacy


OPERATIONAL_COMPILER_CONTRACT = "postgres-semantic-compiler:v0_8"


def compile_document_operational(
    document_input: Mapping[str, Any],
    compiler_context: legacy.CompilerContext,
) -> legacy.DocumentCompilation:
    """Compile one document without constructing the pairwise binding carrier."""

    media_type = legacy.require_text(document_input.get("media_type"), "media_type")
    if (
        media_type not in legacy._TEXT_MEDIA_TYPES
        or legacy._adapter_for(media_type, compiler_context) is None
    ):
        raise ValueError(
            "compile_document_operational requires a declared supported text capability"
        )
    source_text = document_input.get("canonical_text")
    if not isinstance(source_text, str) or not source_text:
        raise ValueError("document_input requires non-empty canonical_text")
    content_sha256 = legacy.require_text(
        document_input.get("content_sha256"), "content_sha256"
    )
    document_ref = legacy.require_text(
        document_input.get("document_ref"), "document_ref"
    )
    source_ref = legacy.require_text(document_input.get("source_ref"), "source_ref")
    if media_type == "text/html":
        canonical = legacy.HtmlDocumentMediaAdapter(
            source_artifact_ref=source_ref
        ).adapt(source_text)
        text = canonical.text
        source_normalisation = {
            "adapter_ref": "media:html:v0_1",
            "canonical_text_ref": canonical.text_id,
            "source_media_type": media_type,
            "warnings": list(canonical.warnings),
            "authority": "normalisation_only",
        }
    else:
        text = source_text
        source_normalisation = {
            "adapter_ref": "media:utf8-text:v0_1",
            "source_media_type": media_type,
            "authority": "normalisation_only",
        }
    if not text:
        raise ValueError("source normalisation produced empty canonical text")
    canonical_text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    context_payload = compiler_context.to_dict()
    build_key_sha256 = legacy.canonical_sha256(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "canonical_text_sha256": canonical_text_sha256,
            "media_adapter_ref": source_normalisation["adapter_ref"],
            "context": context_payload,
            "compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
        }
    )

    parsed_document = legacy.parse_canonical_text(text)
    licensing = legacy.build_mention_licensing_carrier(
        canonical_text=text,
        source_ref=source_ref,
        document_ref=document_ref,
        parsed_document=parsed_document,
    )
    mentions = tuple(licensing["mentions"])
    recurrence = legacy.build_mention_recurrence_carrier(mentions=mentions)
    forms = legacy.build_form_derivation_carrier(mentions=mentions)
    tokens = legacy.tokenize_canonical_with_spans(text)
    layer = legacy.AnnotationLayer(
        layer_ref="annotation-layer:"
        + legacy.canonical_sha256(
            {"document_ref": document_ref, "content": canonical_text_sha256}
        ),
        tokenizer_ref=compiler_context.annotation_backend_ref,
        text_sha256=canonical_text_sha256,
        token_annotations=tuple(
            legacy.TokenAnnotation(index, "canonical_token", token, (source_ref,))
            for index, (token, _start, _end) in enumerate(tokens)
        ),
        span_annotations=tuple(
            legacy.SpanAnnotation(
                span_ref=str(row["mention_ref"]),
                start_token=int(row["start_token"]),
                end_token=int(row["end_token"]),
                annotation_type="licensed_mention",
                value={
                    "generation_reason": row["generation_reason"],
                    "surface": row["canonical_surface"],
                },
                provenance_refs=(source_ref,),
            )
            for row in mentions
        ),
        provenance_refs=(source_ref,),
    )
    semantic_layer, relational_bundle, atom_span_refs = (
        legacy._semantic_annotation_layer(
            document_ref=document_ref,
            source_ref=source_ref,
            content_sha256=canonical_text_sha256,
            tokens=tokens,
            base_layer=layer,
            text=text,
            parsed_document=parsed_document,
        )
    )
    annotation_graph = legacy.AnnotationGraph(
        graph_ref="annotation-graph:"
        + legacy.canonical_sha256(
            {"layers": [layer.to_dict(), semantic_layer.to_dict()]}
        ),
        layers=(layer, semantic_layer),
    )
    declarations = legacy.default_semantic_reduction_declarations()
    atom_mentions = legacy._atom_mention_refs(
        semantic_layer=semantic_layer,
        atom_span_refs=atom_span_refs,
        mentions=mentions,
    )
    parser_observation_refs = legacy._parser_observation_refs_by_mention(
        semantic_layer=semantic_layer,
        mentions=mentions,
    )
    structural_hypotheses = legacy.derive_relational_type_hypotheses(
        bundle=relational_bundle,
        atom_mention_refs=atom_mentions,
        declarations=declarations,
    )
    local_typing = legacy.build_local_typing_carrier(
        mentions=mentions,
        forms=forms["forms"],
        structural_hypotheses=structural_hypotheses,
    )
    unresolved_span_diagnostics = legacy.diagnose_untyped_mentions(
        mentions=mentions,
        local_typing=local_typing,
        bundle=relational_bundle,
        atom_mention_refs=atom_mentions,
        parser_observation_refs=parser_observation_refs,
        parser_capabilities=(parsed_document.get("parser_receipt") or {}).get(
            "capabilities", {}
        ),
    )
    semantic_output = legacy.reduce_relational_bundle(
        document_ref=document_ref,
        bundle=relational_bundle,
        atom_span_refs=atom_span_refs,
        declarations=declarations,
    )
    local_evidence = legacy._local_evidence(
        document_ref=document_ref,
        recurrence=recurrence,
        local_typing=local_typing,
    )
    pnf_graph = legacy._build_pnf_graph(
        document_ref=document_ref,
        mentions=mentions,
        local_types=local_typing["local_type_alternatives"],
        semantic_factors=semantic_output.factors,
        semantic_constraints=semantic_output.constraints,
        semantic_relation_refs=semantic_output.relation_refs,
        source_ref=source_ref,
    )
    constraint_assessments = legacy._constraint_assessments(pnf_graph)
    local_meet_plan, typed_meets, refinements = legacy._local_meets_and_refinements(
        graph=pnf_graph,
        evidence=local_evidence,
        constraint_assessments=constraint_assessments,
    )
    refined_pnf_graph = pnf_graph
    for refinement in refinements:
        refined_pnf_graph = refined_pnf_graph.replace_factor(
            refinement.resulting_factor
        )
    demands = legacy.derive_resolution_demands(refined_pnf_graph)
    artifacts = {
        "canonical_text": text,
        "canonical_text_sha256": canonical_text_sha256,
        "source_normalisation": source_normalisation,
        "build_key_sha256": build_key_sha256,
        "licensing": licensing,
        "recurrence": recurrence,
        "forms": forms,
        "local_typing": local_typing,
        "structural_type_hypotheses": [
            legacy.canonical_json(row) for row in structural_hypotheses
        ],
        "unresolved_span_diagnostics": [
            legacy.canonical_json(row) for row in unresolved_span_diagnostics
        ],
        "unresolved_span_diagnostic_summary": [
            legacy.canonical_json(row)
            for row in legacy.summarize_untyped_diagnostics(
                unresolved_span_diagnostics
            )
        ],
        "annotation_layer": layer.to_dict(),
        "parser_receipt": legacy.canonical_json(
            parsed_document.get("parser_receipt") or {}
        ),
        "annotation_graph": {
            "graph_ref": annotation_graph.graph_ref,
            "layer_refs": [layer.layer_ref, semantic_layer.layer_ref],
        },
        "semantic_annotation_layer": semantic_layer.to_dict(),
        "relational_bundle": legacy.canonical_json(relational_bundle),
        "semantic_reduction_declarations": [
            row.to_dict() for row in declarations
        ],
        "compiler_declarations": [
            legacy.canonical_json(row) for row in legacy._compiler_declarations()
        ],
        "semantic_reduction_refs": list(semantic_output.declaration_refs),
        "semantic_reduction_constraints": [
            row.to_dict() for row in semantic_output.constraints
        ],
        "constraint_assessments": [
            row.to_dict() for row in constraint_assessments
        ],
        "local_evidence": [row.to_dict() for row in local_evidence],
        "local_meet_plan": [
            legacy.canonical_json(row) for row in local_meet_plan
        ],
        "pnf_graph": pnf_graph.to_dict(),
        "refined_pnf_graph": refined_pnf_graph.to_dict(),
        "resolution_demands": [legacy.canonical_json(row) for row in demands],
        "typed_meets": [row.to_dict() for row in typed_meets],
        "factor_refinements": [row.to_dict() for row in refinements],
        "phase_boundary": {
            "completed": ["inventory", "local_compile"],
            "network_performed": False,
            "cross_document_identity_closed": False,
            "readiness_invoked": False,
            "pairwise_binding_evidence_materialized": False,
        },
    }
    operational_artifacts = build_operational_reference_binding_artifacts(artifacts)
    return legacy.DocumentCompilation(
        document_ref=document_ref,
        content_sha256=content_sha256,
        media_type=media_type,
        artifacts=operational_artifacts,
    )


__all__ = [
    "OPERATIONAL_COMPILER_CONTRACT",
    "compile_document_operational",
]
