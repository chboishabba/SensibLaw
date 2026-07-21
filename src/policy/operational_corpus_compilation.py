"""Pairwise-free PostgreSQL operational document compilation.

The active compiler preserves the existing parser, annotation, PNF, constraint, and
demand semantics while exposing document-local work as immutable observation deltas,
revision-bound closure jobs, keyed reductions, and an explicit fixed-point certificate.
No worker mutates a shared graph and no execution result promotes identity or legal truth.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from time import monotonic_ns
from typing import Any, Mapping, Sequence

from src.pnf.factor_proposals import FactorProposal
from src.pnf.operational_reference_binding import (
    build_operational_reference_binding_artifacts,
)
from src.pnf.stage_build_keys import derive_stage_build_keys
from src.pnf.streaming_fixed_point import (
    CoverageNotice,
    PythonClosureExecutor,
    StreamingSemanticOwner,
)
from src.pnf.streaming_operator_executor import (
    STREAMING_OPERATOR_DECLARATION_REF,
    operator_streaming_declaration,
    parser_sentence_deltas,
    solve_operator_job,
)
from src.policy import corpus_compilation as legacy
from src.runtime.stage_timing import StageTimingLedger


OPERATIONAL_COMPILER_CONTRACT = "postgres-semantic-compiler:v0_10"


def _base_proposal_from_factor(
    *,
    document_ref: str,
    source_ref: str,
    factor: Any,
) -> FactorProposal:
    """Project one already-derived base factor without inventing global dependencies."""

    row = factor.to_dict()
    metadata = dict(row.get("metadata") or {})
    provenance_refs = tuple(
        str(ref) for ref in metadata.get("provenance_refs") or ()
    )
    alternatives = [
        dict(value)
        for value in row.get("alternatives") or ()
        if isinstance(value, Mapping)
    ]
    structural_signature = str(
        metadata.get("structural_signature_ref")
        or metadata.get("signature_ref")
        or row.get("factor_type")
        or "semantic.base_factor"
    )
    return FactorProposal(
        document_ref=document_ref,
        source_revision_ref="source-revision:"
        + legacy.canonical_sha256(
            {
                "document_ref": document_ref,
                "source_ref": source_ref,
                "provenance_refs": sorted(provenance_refs),
            }
        ),
        factor_type_ref=str(
            row.get("factor_type") or "semantic.base_factor"
        ),
        source_span_refs=provenance_refs,
        # Base factors are already outputs of the parser-relational reducer.  Their
        # local provenance remains in source_span_refs/candidate_payload; binding
        # every factor to every document observation would recreate a large graph.
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature=structural_signature,
        role_bindings=dict(metadata.get("role_bindings") or {}),
        qualifier_state=dict(metadata.get("qualifier_state") or {}),
        producer_contract=str(
            metadata.get("composition_contract_ref")
            or "semantic-base-proposal:v0_1"
        ),
        declaration_revision="v0_1",
        candidate_payload={
            "source_factor_ref": str(row.get("factor_ref") or ""),
            "alternatives": alternatives,
            "predicate_ref": str(metadata.get("predicate_ref") or ""),
            "provenance_refs": list(provenance_refs),
        },
        residuals=tuple(
            str(value) for value in row.get("residuals") or ()
        ),
    )


def _streaming_semantic_build(
    *,
    document_ref: str,
    source_ref: str,
    observation_deltas: Sequence[Any],
    base_factors: Sequence[Any],
    timings: StageTimingLedger,
    closure_workers: int,
    owner_partitions: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reduce base proposals and stream revision-bound closure receipts."""

    owner = StreamingSemanticOwner(
        document_ref=document_ref,
        partition_count=owner_partitions,
    )
    declaration = operator_streaming_declaration()
    owner.register_declarations((declaration,))
    for delta in observation_deltas:
        owner.admit_observation_delta(delta)

    all_observation_refs = tuple(
        sorted(
            {
                ref
                for delta in observation_deltas
                for ref in delta.observation_refs
            }
        )
    )
    with timings.stage("base_proposal_reduction") as stage:
        base_proposals = tuple(
            _base_proposal_from_factor(
                document_ref=document_ref,
                source_ref=source_ref,
                factor=factor,
            )
            for factor in base_factors
        )
        owner.admit_proposals(base_proposals, stage="base")
        owner.reduce_dirty_groups()
        base_reduction = owner.materialized_reduction
        stage.record(
            input_nodes=len(base_proposals),
            output_nodes=len(base_reduction.factors),
            input_edges=len(base_proposals),
            output_edges=len(base_reduction.factors),
            proposals_generated=len(base_proposals),
            duplicates_collapsed=base_reduction.deduplicated_count,
            alternatives_retained=len(base_reduction.factors),
            residuals_emitted=len(base_reduction.residuals),
        )

    with timings.stage("composition_generation") as stage:
        jobs = owner.drain_ready_jobs()
        closure = PythonClosureExecutor(
            {STREAMING_OPERATOR_DECLARATION_REF: solve_operator_job}
        )
        stage.record(
            input_nodes=len(all_observation_refs),
            output_nodes=len(jobs),
            details={
                "owner_partitions": owner_partitions,
                "closure_workers": closure_workers,
            },
        )

    receipts = []
    reduction_elapsed_ms = 0
    with timings.stage(
        "closure_executor_evaluation",
        backend_ref=closure.backend_ref,
        details={
            "workers": closure_workers,
            "admission_and_reduction_overlap": True,
        },
    ) as closure_stage:
        if jobs:
            with ThreadPoolExecutor(
                max_workers=closure_workers,
                thread_name_prefix="semantic-closure",
            ) as pool:
                futures = {
                    pool.submit(closure.execute, job): job for job in jobs
                }
                for future in as_completed(futures):
                    receipt = future.result()
                    reduction_started = monotonic_ns()
                    owner.admit_solver_receipt(receipt)
                    # Each returned delta is reduced immediately.  The reduction
                    # duration is also recorded separately as overlapping work.
                    owner.reduce_dirty_groups()
                    reduction_elapsed_ms += max(
                        0,
                        (monotonic_ns() - reduction_started) // 1_000_000,
                    )
                    receipts.append(receipt)
        closure_stage.record(
            input_nodes=sum(len(job.input_refs) for job in jobs),
            output_nodes=sum(len(row.proposals) for row in receipts),
            proposals_generated=sum(
                len(row.proposals) for row in receipts
            ),
            details={"job_count": len(jobs)},
        )

    materialized = owner.materialized_reduction
    timings.append(
        stage="composition_proposal_reduction",
        elapsed_ms=reduction_elapsed_ms,
        input_nodes=len(base_proposals)
        + sum(len(row.proposals) for row in receipts),
        output_nodes=len(materialized.factors),
        input_edges=len(base_proposals)
        + sum(len(row.proposals) for row in receipts),
        output_edges=len(materialized.factors),
        alternatives_retained=len(materialized.factors),
        residuals_emitted=len(materialized.residuals),
        details={
            "overlaps_with": "closure_executor_evaluation",
            "streamed_receipt_count": len(receipts),
        },
    )

    owner.admit_coverage_notice(
        CoverageNotice(
            document_ref=document_ref,
            scope_ref="document-global",
            barrier="document",
            state="complete",
            evidence_refs=tuple(
                delta.delta_ref for delta in observation_deltas
            ),
        )
    )
    certificate = owner.fixed_point_certificate()
    if not certificate.local_fixed_point_reached:
        raise ValueError(
            "streaming semantic owner did not reach a local fixed point"
        )

    scopes = sorted({delta.scope_ref for delta in observation_deltas})
    build = {
        **owner.to_dict(),
        "region_boundary_summaries": [
            owner.region_boundary_summary(scope).to_dict()
            for scope in scopes
        ],
        "fixed_point_certificate": certificate.to_dict(),
        "declarations": [declaration.to_dict()],
        "closure_backend": closure.backend_ref,
        "streaming_bidirectional": True,
        "logical_owner_granularity": "document_scope_factor_family",
        "eventual_consistency": "convergent_append_only",
        "materialized_view_authority": (
            "deterministic_candidate_projection"
        ),
    }
    metrics: dict[str, Any] = {
        "observation_delta_count": len(observation_deltas),
        "observation_count": len(all_observation_refs),
        "observation_refs": all_observation_refs,
        "base_proposal_count": len(base_proposals),
        "base_proposal_refs": tuple(
            row.proposal_ref for row in base_proposals
        ),
        "base_factor_count": len(base_reduction.factors),
        "base_factor_refs": tuple(
            row.factor_ref for row in base_reduction.factors
        ),
        "base_residual_count": len(base_reduction.residuals),
        "closure_job_count": len(jobs),
        "derived_proposal_count": sum(
            len(row.proposals) for row in receipts
        ),
        "derived_proposal_refs": tuple(
            sorted(
                proposal.proposal_ref
                for receipt in receipts
                for proposal in receipt.proposals
            )
        ),
        "materialized_factor_count": len(materialized.factors),
        "materialized_factor_refs": tuple(
            row.factor_ref for row in materialized.factors
        ),
        "materialized_residual_count": len(materialized.residuals),
    }
    return build, metrics


def compile_document_operational(
    document_input: Mapping[str, Any],
    compiler_context: legacy.CompilerContext,
    *,
    closure_workers: int = 2,
    owner_partitions: int = 2,
) -> legacy.DocumentCompilation:
    """Compile one document through the streaming local fixed-point boundary."""

    if not 1 <= closure_workers <= 32:
        raise ValueError("closure_workers must be between 1 and 32")
    if not 1 <= owner_partitions <= 128:
        raise ValueError("owner_partitions must be between 1 and 128")
    media_type = legacy.require_text(
        document_input.get("media_type"),
        "media_type",
    )
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
        document_input.get("content_sha256"),
        "content_sha256",
    )
    document_ref = legacy.require_text(
        document_input.get("document_ref"),
        "document_ref",
    )
    source_ref = legacy.require_text(
        document_input.get("source_ref"),
        "source_ref",
    )
    timings = StageTimingLedger(document_ref=document_ref)

    with timings.stage("canonical_normalization") as stage:
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
        canonical_text_sha256 = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
        stage.record(
            input_nodes=len(source_text),
            output_nodes=len(text),
        )

    context_payload = compiler_context.to_dict()
    build_key_sha256 = legacy.canonical_sha256(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "canonical_text_sha256": canonical_text_sha256,
            "media_adapter_ref": source_normalisation["adapter_ref"],
            "context": context_payload,
            "compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
            "closure_workers_semantic_effect": "none",
            "owner_partitions_semantic_effect": "none",
        }
    )

    with timings.stage(
        "parser_annotation",
        backend_ref="spacy",
        details={
            "annotation_backend_ref": compiler_context.annotation_backend_ref
        },
    ) as stage:
        parsed_document = legacy.parse_canonical_text(text)
        parsed_token_count = sum(
            len(sentence.get("tokens") or ())
            for sentence in parsed_document.get("sents") or ()
        )
        stage.record(
            tokens_processed=parsed_token_count,
            output_nodes=parsed_token_count,
        )

    with timings.stage("coordinate_validation") as stage:
        tokens = legacy.tokenize_canonical_with_spans(text)
        stage.record(
            tokens_processed=len(tokens),
            output_nodes=len(tokens),
        )

    with timings.stage("mention_licensing") as stage:
        licensing = legacy.build_mention_licensing_carrier(
            canonical_text=text,
            source_ref=source_ref,
            document_ref=document_ref,
            parsed_document=parsed_document,
        )
        mentions = tuple(licensing["mentions"])
        recurrence = legacy.build_mention_recurrence_carrier(
            mentions=mentions
        )
        forms = legacy.build_form_derivation_carrier(mentions=mentions)
        stage.record(
            input_nodes=len(tokens),
            output_nodes=len(mentions),
            tokens_processed=len(tokens),
            details={"form_count": len(forms.get("forms") or ())},
        )

    layer = legacy.AnnotationLayer(
        layer_ref="annotation-layer:"
        + legacy.canonical_sha256(
            {
                "document_ref": document_ref,
                "content": canonical_text_sha256,
            }
        ),
        tokenizer_ref=compiler_context.annotation_backend_ref,
        text_sha256=canonical_text_sha256,
        token_annotations=tuple(
            legacy.TokenAnnotation(
                index,
                "canonical_token",
                token,
                (source_ref,),
            )
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

    with timings.stage("parser_observation_projection") as stage:
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
        parser_deltas = parser_sentence_deltas(
            document_ref=document_ref,
            parsed_document=parsed_document,
        )
        observation_count = sum(
            len(row.observation_refs) for row in parser_deltas
        )
        stage.record(
            input_nodes=len(tokens),
            output_nodes=observation_count,
            tokens_processed=len(tokens),
            details={"delta_count": len(parser_deltas)},
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
        parser_capabilities=(
            parsed_document.get("parser_receipt") or {}
        ).get("capabilities", {}),
    )

    with timings.stage("base_proposal_generation") as stage:
        semantic_output = legacy.reduce_relational_bundle(
            document_ref=document_ref,
            bundle=relational_bundle,
            atom_span_refs=atom_span_refs,
            declarations=declarations,
        )
        stage.record(
            input_nodes=len(relational_bundle.get("atoms") or ()),
            output_nodes=len(semantic_output.factors),
            proposals_generated=len(semantic_output.factors),
            input_edges=len(relational_bundle.get("relations") or ()),
            output_edges=len(semantic_output.relation_refs),
        )

    streaming_build, streaming_metrics = _streaming_semantic_build(
        document_ref=document_ref,
        source_ref=source_ref,
        observation_deltas=parser_deltas,
        base_factors=semantic_output.factors,
        timings=timings,
        closure_workers=closure_workers,
        owner_partitions=owner_partitions,
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

    with timings.stage("constraint_fixed_point") as stage:
        constraint_assessments = legacy._constraint_assessments(pnf_graph)
        local_meet_plan, typed_meets, refinements = (
            legacy._local_meets_and_refinements(
                graph=pnf_graph,
                evidence=local_evidence,
                constraint_assessments=constraint_assessments,
            )
        )
        refined_pnf_graph = pnf_graph
        for refinement in refinements:
            refined_pnf_graph = refined_pnf_graph.replace_factor(
                refinement.resulting_factor
            )
        stage.record(
            input_nodes=len(pnf_graph.factors),
            output_nodes=len(refined_pnf_graph.factors),
            input_edges=len(constraint_assessments),
            output_edges=len(refinements),
            residuals_emitted=sum(
                len(row.resulting_factor.residuals)
                for row in refinements
            ),
        )

    demands = legacy.derive_resolution_demands(refined_pnf_graph)
    stage_keys = derive_stage_build_keys(
        canonical_text_digest=canonical_text_sha256,
        parser_contract_ref=str(
            (parsed_document.get("parser_receipt") or {}).get(
                "contract_ref"
            )
            or compiler_context.annotation_backend_ref
        ),
        observation_refs=streaming_metrics["observation_refs"],
        base_proposal_refs=streaming_metrics["base_proposal_refs"],
        base_factor_refs=streaming_metrics["base_factor_refs"],
        declaration_refs=(
            *(row.declaration_ref for row in declarations),
            STREAMING_OPERATOR_DECLARATION_REF,
        ),
        derived_proposal_refs=streaming_metrics[
            "derived_proposal_refs"
        ],
        materialized_factor_refs=streaming_metrics[
            "materialized_factor_refs"
        ],
        constraint_refs=(
            row.constraint_ref for row in semantic_output.constraints
        ),
    )

    artifacts = {
        "canonical_text": text,
        "canonical_text_sha256": canonical_text_sha256,
        "source_normalisation": source_normalisation,
        "build_key_sha256": build_key_sha256,
        "stage_build_keys": stage_keys.to_dict(),
        "licensing": licensing,
        "recurrence": recurrence,
        "forms": forms,
        "local_typing": local_typing,
        "structural_type_hypotheses": [
            legacy.canonical_json(row) for row in structural_hypotheses
        ],
        "unresolved_span_diagnostics": [
            legacy.canonical_json(row)
            for row in unresolved_span_diagnostics
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
            legacy.canonical_json(row)
            for row in legacy._compiler_declarations()
        ],
        "semantic_reduction_refs": list(
            semantic_output.declaration_refs
        ),
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
        "resolution_demands": [
            legacy.canonical_json(row) for row in demands
        ],
        "typed_meets": [row.to_dict() for row in typed_meets],
        "factor_refinements": [
            row.to_dict() for row in refinements
        ],
        "streaming_semantic_build": streaming_build,
        "semantic_stage_timing": timings.to_dict(),
        "semantic_runtime_configuration": {
            "closure_workers": closure_workers,
            "owner_partitions": owner_partitions,
            "semantic_effect": "none",
        },
        "phase_boundary": {
            "completed": [
                "inventory",
                "local_compile",
                "local_fixed_point",
            ],
            "network_performed": False,
            "cross_document_identity_closed": False,
            "readiness_invoked": False,
            "pairwise_binding_evidence_materialized": False,
            "streaming_bidirectional": True,
            "shared_graph_mutation": False,
        },
    }
    operational_artifacts = build_operational_reference_binding_artifacts(
        artifacts
    )
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
