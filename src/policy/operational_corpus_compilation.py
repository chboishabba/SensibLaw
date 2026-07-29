"""Pairwise-free PostgreSQL operational document compilation.

The active compiler preserves the existing parser, annotation, PNF, constraint, and
demand semantics while exposing document-local work as immutable observation deltas,
revision-bound closure jobs, keyed reductions, and an explicit fixed-point certificate.
No worker mutates a shared graph and no execution result promotes identity or legal truth.
"""

from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.pnf.document_fibres import (
    DOCUMENT_FIBRE_CONTRACT,
    DocumentFibre,
    DocumentFibrePolicy,
    parse_document_fibres,
)
from src.pnf.document_projection_manifests import (
    build_logical_layer_manifest,
    build_partition_manifest,
    document_projection_join,
    partition_layer_records,
)
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
from src.policy.artifact_projection import ArtifactProjectionPolicy, project_artifacts
from src.runtime.document_stage_metrics import stage_measure_declaration
from src.runtime.active_document_resources import (
    ActiveDocumentResourceGuard,
    GuardedDocumentProgress,
    NullDocumentProgress,
)
from src.runtime.stage_timing import StageTimingLedger


def _annotation_layer_records(layer: Any) -> dict[str, Any]:
    """Project one layer without a whole-layer ``to_dict`` allocation."""

    return {
        "schema_version": "sl.annotation_layer.v0_1",
        "layer_ref": layer.layer_ref,
        "tokenizer_ref": layer.tokenizer_ref,
        "text_sha256": layer.text_sha256,
        "token_annotations": [
            row.to_dict()
            for row in sorted(
                layer.token_annotations,
                key=lambda value: (value.token_index, value.annotation_type),
            )
        ],
        "span_annotations": [
            row.to_dict()
            for row in sorted(
                layer.span_annotations,
                key=lambda value: (
                    value.start_token,
                    value.end_token,
                    value.span_ref,
                ),
            )
        ],
        "relation_annotations": [
            row.to_dict()
            for row in sorted(
                layer.relation_annotations,
                key=lambda value: value.relation_ref,
            )
        ],
        "provenance_refs": sorted(layer.provenance_refs),
        "authority": "annotation_only",
    }


def _pnf_graph_records(graph: Any) -> dict[str, Any]:
    """Project graph record families without a whole-graph ``to_dict`` call."""

    return {
        "schema_version": "sl.pnf_graph.v0_1",
        "graph_ref": graph.graph_ref,
        "document_ref": graph.document_ref,
        "factors": [
            row.to_dict()
            for row in sorted(graph.factors, key=lambda value: value.factor_ref)
        ],
        "constraints": [
            row.to_dict()
            for row in sorted(graph.constraints, key=lambda value: value.constraint_ref)
        ],
        "relation_refs": sorted(graph.relation_refs),
        "residuals": sorted(graph.residuals),
        "authority": "candidate_only",
    }


OPERATIONAL_COMPILER_CONTRACT = "postgres-semantic-compiler:v0_11"
DOCUMENT_COMPILE_STAGE_NAMES = (
    "canonical_normalization",
    "parser_annotation",
    "coordinate_validation",
    "mention_licensing",
    "parser_observation_projection",
    "local_typing_diagnostics",
    "base_proposal_generation",
    "streaming_closure",
    "pnf_graph_construction",
    "constraint_assessment",
    "meet_refinement",
    "demand_derivation",
)
DOCUMENT_COMPILE_STAGE_COUNT = len(DOCUMENT_COMPILE_STAGE_NAMES)


@contextmanager
def _document_stage_progress(
    progress: Any | None,
    stage: str,
    *,
    totals: Mapping[str, int | float | None] | None = None,
    details: Mapping[str, Any] | None = None,
    subject_ref: str | None = None,
    worker: str | None = None,
):
    if progress is None or not hasattr(progress, "stage"):
        yield None
        return
    with progress.stage(
        stage,
        measures=stage_measure_declaration(stage, totals=totals),
        details=details,
        subject_ref=subject_ref,
        worker=worker,
    ) as handle:
        yield handle


def _base_proposal_from_factor(
    *,
    document_ref: str,
    source_ref: str,
    factor: Any,
) -> FactorProposal:
    """Project one already-derived base factor without inventing global dependencies."""

    row = factor.to_dict()
    metadata = dict(row.get("metadata") or {})
    provenance_refs = tuple(str(ref) for ref in metadata.get("provenance_refs") or ())
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
        factor_type_ref=str(row.get("factor_type") or "semantic.base_factor"),
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
            metadata.get("composition_contract_ref") or "semantic-base-proposal:v0_1"
        ),
        declaration_revision="v0_1",
        candidate_payload={
            "source_factor_ref": str(row.get("factor_ref") or ""),
            "alternatives": alternatives,
            "predicate_ref": str(metadata.get("predicate_ref") or ""),
            "provenance_refs": list(provenance_refs),
        },
        residuals=tuple(str(value) for value in row.get("residuals") or ()),
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
    progress_observer: Any | None = None,
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
        sorted({ref for delta in observation_deltas for ref in delta.observation_refs})
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
                futures = {pool.submit(closure.execute, job): job for job in jobs}
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
                    if progress_observer is not None:
                        progress_observer(
                            {
                                "jobs_completed": len(receipts),
                                "input_refs_processed": sum(
                                    len(row.input_refs) for row in receipts
                                ),
                                "proposals_emitted": sum(
                                    len(row.proposals) for row in receipts
                                ),
                            }
                        )
        closure_stage.record(
            input_nodes=sum(len(job.input_refs) for job in jobs),
            output_nodes=sum(len(row.proposals) for row in receipts),
            proposals_generated=sum(len(row.proposals) for row in receipts),
            details={"job_count": len(jobs)},
        )

    materialized = owner.materialized_reduction
    timings.append(
        stage="composition_proposal_reduction",
        elapsed_ms=reduction_elapsed_ms,
        input_nodes=len(base_proposals) + sum(len(row.proposals) for row in receipts),
        output_nodes=len(materialized.factors),
        input_edges=len(base_proposals) + sum(len(row.proposals) for row in receipts),
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
            evidence_refs=tuple(delta.delta_ref for delta in observation_deltas),
        )
    )
    certificate = owner.fixed_point_certificate()
    if not certificate.local_fixed_point_reached:
        raise ValueError("streaming semantic owner did not reach a local fixed point")

    scopes = sorted({delta.scope_ref for delta in observation_deltas})
    build = {
        **owner.to_dict(),
        "region_boundary_summaries": [
            owner.region_boundary_summary(scope).to_dict() for scope in scopes
        ],
        "fixed_point_certificate": certificate.to_dict(),
        "declarations": [declaration.to_dict()],
        "closure_backend": closure.backend_ref,
        "streaming_bidirectional": True,
        "logical_owner_granularity": "document_scope_factor_family",
        "eventual_consistency": "convergent_append_only",
        "materialized_view_authority": ("deterministic_candidate_projection"),
    }
    metrics: dict[str, Any] = {
        "observation_delta_count": len(observation_deltas),
        "observation_count": len(all_observation_refs),
        "observation_refs": all_observation_refs,
        "base_proposal_count": len(base_proposals),
        "base_proposal_refs": tuple(row.proposal_ref for row in base_proposals),
        "base_factor_count": len(base_reduction.factors),
        "base_factor_refs": tuple(row.factor_ref for row in base_reduction.factors),
        "base_residual_count": len(base_reduction.residuals),
        "closure_job_count": len(jobs),
        "derived_proposal_count": sum(len(row.proposals) for row in receipts),
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
    parser_workers: int = 2,
    parser_limit_chars: int = 1_000_000,
    parser_target_chars: int = 400_000,
    parser_overlap_chars: int = 8_192,
    parser_checkpoint_dir: str | None = None,
    progress: Any | None = None,
    artifact_projection_policy: ArtifactProjectionPolicy | None = None,
    projection_partition_persistence: Callable[[Sequence[Mapping[str, Any]]], None]
    | None = None,
) -> legacy.DocumentCompilation:
    """Compile one document through the streaming local fixed-point boundary."""

    if not 1 <= closure_workers <= 32:
        raise ValueError("closure_workers must be between 1 and 32")
    if not 1 <= owner_partitions <= 128:
        raise ValueError("owner_partitions must be between 1 and 128")
    parser_policy = DocumentFibrePolicy(
        workers=parser_workers,
        parser_limit_chars=parser_limit_chars,
        target_chars=parser_target_chars,
        overlap_chars=parser_overlap_chars,
    )
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
    resource_guard = ActiveDocumentResourceGuard(document_ref=document_ref)
    progress = GuardedDocumentProgress(
        progress
        if progress is not None and hasattr(progress, "stage")
        else NullDocumentProgress(),
        resource_guard,
    )

    with timings.stage("canonical_normalization") as stage:
        with _document_stage_progress(
            progress,
            "canonical_normalization",
            totals={
                "input_chars": len(source_text),
                "output_chars": len(source_text),
                "input_bytes": len(source_text.encode("utf-8")),
                "output_bytes": len(source_text.encode("utf-8")),
            },
        ) as progress_stage:
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
            if progress_stage is not None:
                progress_stage.observe(
                    measures={
                        "input_chars": len(source_text),
                        "output_chars": len(text),
                        "input_bytes": len(source_text.encode("utf-8")),
                        "output_bytes": len(text.encode("utf-8")),
                    },
                    details={
                        "input_nodes": len(source_text),
                        "output_nodes": len(text),
                    },
                )
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
            "document_fibre_contract": DOCUMENT_FIBRE_CONTRACT,
            "document_fibre_policy": parser_policy.to_dict(),
            "closure_workers_semantic_effect": "none",
            "owner_partitions_semantic_effect": "none",
        }
    )

    with timings.stage(
        "parser_annotation",
        backend_ref="spacy",
        details={"annotation_backend_ref": compiler_context.annotation_backend_ref},
    ) as stage:
        with _document_stage_progress(
            progress,
            "parser_annotation",
            totals={"fibres": 1},
            details={"annotation_backend_ref": compiler_context.annotation_backend_ref},
        ) as progress_stage:
            parsed_document = parse_document_fibres(
                document_ref=document_ref,
                canonical_text=text,
                parser=legacy.parse_canonical_text,
                policy=parser_policy,
                checkpoint_dir=parser_checkpoint_dir,
                progress=progress_stage,
            )
        parsed_token_count = sum(
            len(sentence.get("tokens") or ())
            for sentence in parsed_document.get("sents") or ()
        )
        stage.record(
            tokens_processed=parsed_token_count,
            output_nodes=parsed_token_count,
        )

    with timings.stage("coordinate_validation") as stage:
        with _document_stage_progress(
            progress,
            "coordinate_validation",
            totals={"tokens_checked": len(text)},
        ) as progress_stage:
            tokens = legacy.tokenize_canonical_with_spans(text)
            if progress_stage is not None:
                progress_stage.observe(
                    measures={
                        "tokens_checked": len(tokens),
                        "spans_checked": len(tokens),
                        "coordinates_rejected": 0,
                    },
                    details={
                        "tokens_processed": len(tokens),
                        "output_nodes": len(tokens),
                    },
                )
        stage.record(
            tokens_processed=len(tokens),
            output_nodes=len(tokens),
        )

    with timings.stage("mention_licensing") as stage:
        with _document_stage_progress(
            progress,
            "mention_licensing",
            totals={"mentions_licensed": len(tokens)},
        ) as progress_stage:

            def observe_mention_work(measures: Mapping[str, Any]) -> None:
                if (
                    progress_stage is not None
                    and getattr(progress_stage, "active_stage", None)
                    == "mention_licensing"
                ):
                    progress_stage.observe(measures=measures)

            licensing = legacy.build_mention_licensing_carrier(
                canonical_text=text,
                source_ref=source_ref,
                document_ref=document_ref,
                parsed_document=parsed_document,
                tokens=tokens,
                progress_observer=observe_mention_work,
            )
            mentions = tuple(licensing["mentions"])
            recurrence = legacy.build_mention_recurrence_carrier(mentions=mentions)
            forms = legacy.build_form_derivation_carrier(mentions=mentions)
            if (
                progress_stage is not None
                and getattr(progress_stage, "active_stage", None) == "mention_licensing"
            ):
                progress_stage.observe(
                    measures={
                        "tokens_scanned": len(tokens),
                        "mentions_considered": len(mentions),
                        "mentions_licensed": len(mentions),
                        "recurrences_derived": len(recurrence.get("recurrences") or ()),
                        "forms_derived": len(forms.get("forms") or ()),
                    },
                    details={"form_count": len(forms.get("forms") or ())},
                )
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
        with _document_stage_progress(
            progress,
            "parser_observation_projection",
            totals={"observations_emitted": len(tokens)},
        ) as progress_stage:
            semantic_layer, relational_bundle, atom_span_refs = (
                legacy._semantic_annotation_layer(
                    document_ref=document_ref,
                    source_ref=source_ref,
                    content_sha256=canonical_text_sha256,
                    tokens=tokens,
                    base_layer=layer,
                    text=text,
                    parsed_document=parsed_document,
                    progress_observer=(
                        lambda measures: (
                            progress_stage.observe(measures=measures)
                            if progress_stage is not None
                            and getattr(progress_stage, "active_stage", None)
                            == "parser_observation_projection"
                            else None
                        )
                    ),
                )
            )
            parser_deltas = parser_sentence_deltas(
                document_ref=document_ref,
                parsed_document=parsed_document,
            )
            base_logical_layer = build_logical_layer_manifest(
                document_ref=document_ref,
                source_sha256=canonical_text_sha256,
                layer=layer,
            )
            semantic_logical_layer = build_logical_layer_manifest(
                document_ref=document_ref,
                source_sha256=canonical_text_sha256,
                layer=semantic_layer,
            )
            # Graph identity is ref-only.  The payload layers remain available
            # to the existing document reducer but are never serialised to
            # construct their graph identity.
            annotation_graph = legacy.AnnotationGraph.from_layer_refs(
                (base_logical_layer.layer_ref, semantic_logical_layer.layer_ref)
            )
            observation_count = sum(len(row.observation_refs) for row in parser_deltas)
            if progress_stage is not None:
                resource_snapshot = resource_guard.checkpoint(
                    stage="parser_observation_projection",
                    current_kernel="annotation_graph_identity",
                )
                progress_stage.observe(
                    measures={
                        "sentences_projected": len(parsed_document.get("sents") or ()),
                        "observations_emitted": observation_count,
                        "deltas_emitted": len(parser_deltas),
                        "relations_projected": len(
                            relational_bundle.get("relations") or ()
                        ),
                        **resource_snapshot["resources"],
                        "retained_object_counts": (
                            len(layer.token_annotations)
                            + len(layer.span_annotations)
                            + len(semantic_layer.token_annotations)
                            + len(semantic_layer.span_annotations)
                            + len(semantic_layer.relation_annotations)
                        ),
                    },
                    details={
                        "delta_count": len(parser_deltas),
                        "current_kernel": "annotation_graph_identity",
                        "annotation_graph_ref": annotation_graph.graph_ref,
                    },
                    message="annotation_graph_identity",
                )
        stage.record(
            input_nodes=len(tokens),
            output_nodes=observation_count,
            tokens_processed=len(tokens),
            details={"delta_count": len(parser_deltas)},
        )

    declarations = legacy.default_semantic_reduction_declarations()
    with _document_stage_progress(
        progress,
        "local_typing_diagnostics",
        totals={
            "mentions_considered": len(mentions),
            "typing_hypotheses_derived": len(relational_bundle.get("atoms") or ()),
            "diagnostics_evaluated": len(mentions),
        },
    ) as progress_stage:
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
        if progress_stage is not None:
            progress_stage.observe(
                measures={
                    "mentions_considered": len(mentions),
                    "typing_hypotheses_derived": len(structural_hypotheses),
                    "diagnostics_evaluated": len(unresolved_span_diagnostics),
                },
                details={
                    "atom_mention_refs": len(atom_mentions),
                    "parser_observation_ref_mentions": len(parser_observation_refs),
                    "local_type_alternatives": len(
                        local_typing.get("local_type_alternatives") or ()
                    ),
                },
            )
        # These lookup maps feed only local typing/diagnostics.  Keep their
        # derived carriers, but release the document-wide intermediate maps
        # before the resource gate that protects streaming closure.
        del atom_mentions
        del parser_observation_refs

    with timings.stage("base_proposal_generation") as stage:
        with _document_stage_progress(
            progress,
            "base_proposal_generation",
            totals={
                "atoms_scanned": len(relational_bundle.get("atoms") or ()),
            },
        ) as progress_stage:
            semantic_output = legacy.reduce_relational_bundle(
                document_ref=document_ref,
                bundle=relational_bundle,
                atom_span_refs=atom_span_refs,
                declarations=declarations,
            )
            if progress_stage is not None:
                progress_stage.observe(
                    measures={
                        "atoms_scanned": len(relational_bundle.get("atoms") or ()),
                        "relations_scanned": len(
                            relational_bundle.get("relations") or ()
                        ),
                        "proposals_generated": len(semantic_output.factors),
                        "factors_emitted": len(semantic_output.factors),
                        "constraints_emitted": len(semantic_output.constraints),
                    },
                    details={
                        "input_nodes": len(relational_bundle.get("atoms") or ()),
                        "output_nodes": len(semantic_output.factors),
                        "output_edges": len(semantic_output.relation_refs),
                    },
                )
        stage.record(
            input_nodes=len(relational_bundle.get("atoms") or ()),
            output_nodes=len(semantic_output.factors),
            proposals_generated=len(semantic_output.factors),
            input_edges=len(relational_bundle.get("relations") or ()),
            output_edges=len(semantic_output.relation_refs),
        )
    del atom_span_refs

    with _document_stage_progress(
        progress,
        "streaming_closure",
        totals={"jobs_completed": None},
    ) as progress_stage:
        # No closure job may allocate from an already pressured projection.
        # This is deliberately a restart-from-document boundary: changing the
        # fibre policy after pressure would change execution policy silently.
        resource_guard.checkpoint(
            stage="streaming_closure",
            current_kernel="artifact_projection",
            retained_indexes=(
                len(parser_deltas)
                + len(semantic_output.factors)
                + len(relational_bundle.get("relations") or ())
            ),
            fail_on_soft_pressure=True,
        )

        def observe_closure_progress(payload: Mapping[str, Any]) -> None:
            if progress_stage is None:
                return
            measures = dict(payload)
            current_kernel = str(measures.pop("current_kernel", "streaming_closure"))
            progress_stage.observe(
                measures=measures,
                details={"current_kernel": current_kernel},
                message=current_kernel,
            )

        streaming_build, streaming_metrics = _streaming_semantic_build(
            document_ref=document_ref,
            source_ref=source_ref,
            observation_deltas=parser_deltas,
            base_factors=semantic_output.factors,
            timings=timings,
            closure_workers=closure_workers,
            owner_partitions=owner_partitions,
            progress_observer=observe_closure_progress,
        )
        if progress_stage is not None:
            progress_stage.observe(
                measures={
                    "jobs_completed": streaming_metrics["closure_job_count"],
                    "proposals_emitted": streaming_metrics["derived_proposal_count"],
                    "dirty_groups_reduced": streaming_metrics[
                        "materialized_factor_count"
                    ],
                }
            )

    local_evidence = legacy._local_evidence(
        document_ref=document_ref,
        recurrence=recurrence,
        local_typing=local_typing,
    )
    with _document_stage_progress(
        progress,
        "pnf_graph_construction",
        totals={
            "factors_materialized": len(semantic_output.factors),
            "constraints_materialized": len(semantic_output.constraints),
            "relations_materialized": len(semantic_output.relation_refs),
        },
    ) as progress_stage:
        pnf_graph = legacy._build_pnf_graph(
            document_ref=document_ref,
            mentions=mentions,
            local_types=local_typing["local_type_alternatives"],
            semantic_factors=semantic_output.factors,
            semantic_constraints=semantic_output.constraints,
            semantic_relation_refs=semantic_output.relation_refs,
            source_ref=source_ref,
        )
        if progress_stage is not None:
            progress_stage.observe(
                measures={
                    "factors_materialized": len(pnf_graph.factors),
                    "constraints_materialized": len(pnf_graph.constraints),
                    "relations_materialized": len(pnf_graph.relation_refs),
                    "residuals_materialized": sum(
                        len(row.residuals) for row in pnf_graph.factors
                    ),
                }
            )

    with timings.stage("constraint_fixed_point") as stage:
        with _document_stage_progress(
            progress,
            "constraint_assessment",
            totals={"constraints_evaluated": len(pnf_graph.constraints)},
        ) as assessment_progress:
            constraint_assessments = legacy._constraint_assessments(pnf_graph)
            if assessment_progress is not None:
                assessment_progress.observe(
                    measures={
                        "constraints_evaluated": len(constraint_assessments),
                        "assessments_emitted": len(constraint_assessments),
                    }
                )
        with _document_stage_progress(
            progress,
            "meet_refinement",
            totals={"candidate_meets_considered": len(constraint_assessments)},
        ) as refinement_progress:
            local_meet_plan, typed_meets, refinements = (
                legacy._local_meets_and_refinements(
                    graph=pnf_graph,
                    evidence=local_evidence,
                    constraint_assessments=constraint_assessments,
                )
            )
            if refinement_progress is not None:
                refinement_progress.observe(
                    measures={
                        "candidate_meets_considered": len(constraint_assessments),
                        "typed_meets_accepted": len(typed_meets),
                        "refinements_proposed": len(refinements),
                        "refinements_applied": len(refinements),
                    }
                )
        refined_pnf_graph = pnf_graph.replace_factors(
            [refinement.resulting_factor for refinement in refinements]
        )
        stage.record(
            input_nodes=len(pnf_graph.factors),
            output_nodes=len(refined_pnf_graph.factors),
            input_edges=len(constraint_assessments),
            output_edges=len(refinements),
            residuals_emitted=sum(
                len(row.resulting_factor.residuals) for row in refinements
            ),
        )

    with _document_stage_progress(
        progress,
        "demand_derivation",
        totals={"factors_scanned": len(refined_pnf_graph.factors)},
    ) as progress_stage:
        demands = legacy.derive_resolution_demands(refined_pnf_graph)
        if progress_stage is not None:
            progress_stage.observe(
                measures={
                    "factors_scanned": len(refined_pnf_graph.factors),
                    "demands_emitted": len(demands),
                    "demands_unresolved": len(demands),
                }
            )
    parser_receipt = legacy.canonical_json(parsed_document.get("parser_receipt") or {})
    cross_fibre_demands = list(parser_receipt.get("cross_fibre_demands") or ())
    cross_fibre_fixed_point = dict(parser_receipt.get("cross_fibre_fixed_point") or {})
    stage_keys = derive_stage_build_keys(
        canonical_text_digest=canonical_text_sha256,
        parser_contract_ref=str(
            (parsed_document.get("parser_receipt") or {}).get("contract_ref")
            or compiler_context.annotation_backend_ref
        ),
        observation_refs=streaming_metrics["observation_refs"],
        base_proposal_refs=streaming_metrics["base_proposal_refs"],
        base_factor_refs=streaming_metrics["base_factor_refs"],
        declaration_refs=(
            *(row.declaration_ref for row in declarations),
            STREAMING_OPERATOR_DECLARATION_REF,
        ),
        derived_proposal_refs=streaming_metrics["derived_proposal_refs"],
        materialized_factor_refs=streaming_metrics["materialized_factor_refs"],
        constraint_refs=(row.constraint_ref for row in semantic_output.constraints),
    )

    # These manifests are execution/persistence partitions only.  The join is
    # intentionally completed here, before any document-level semantic output
    # is published; no partition can be treated as a semantic document.
    carrier_row = parser_receipt.get("document_structural_carrier") or {}
    fibre_rows = carrier_row.get("fibres") or ()
    if not fibre_rows:
        fibre_rows = (
            {
                "document_ref": document_ref,
                "fibre_ref": "document-fibre:whole_document",
                "sequence_no": 0,
                "owner_start": 0,
                "owner_end": len(text),
                "context_start": 0,
                "context_end": len(text),
                "text_sha256": canonical_text_sha256,
            },
        )
    carrier_ref = str(
        carrier_row.get("carrier_ref") or "document-structural-carrier:whole_document"
    )
    bundle_ref = "relational-bundle:" + legacy.canonical_sha256(relational_bundle)
    token_char_spans = tuple((start, end) for _token, start, end in tokens)
    partitions = []
    for row in fibre_rows:
        fibre_values = dict(row)
        fibre_values.pop("schema_version", None)
        fibre = DocumentFibre(**fibre_values)
        base_annotation_refs, base_relation_refs = partition_layer_records(
            layer=layer,
            token_char_spans=token_char_spans,
            fibre=fibre,
            partition_count=len(fibre_rows),
        )
        semantic_annotation_refs, semantic_relation_refs = partition_layer_records(
            layer=semantic_layer,
            token_char_spans=token_char_spans,
            fibre=fibre,
            partition_count=len(fibre_rows),
        )
        demand_refs = tuple(
            str(value.get("demand_ref"))
            for value in cross_fibre_demands
            if isinstance(value, Mapping)
            and str(value.get("source_fibre_ref") or fibre.fibre_ref) == fibre.fibre_ref
            and value.get("demand_ref")
        )
        observation_refs = tuple(
            delta.delta_ref
            for delta, sentence in zip(
                parser_deltas, parsed_document.get("sents") or (), strict=False
            )
            if str(sentence.get("fibre_ref") or fibre.fibre_ref) == fibre.fibre_ref
        )
        partitions.append(
            build_partition_manifest(
                fibre=fibre,
                carrier_ref=carrier_ref,
                source_sha256=canonical_text_sha256,
                build_key_sha256=build_key_sha256,
                parser_contract_ref=str(
                    parser_receipt.get("contract_ref")
                    or compiler_context.annotation_backend_ref
                ),
                reducer_contract_ref="semantic-relational-reducer:v0_1",
                annotation_record_refs=(
                    *base_annotation_refs,
                    *semantic_annotation_refs,
                ),
                relation_record_refs=(*base_relation_refs, *semantic_relation_refs),
                parser_observation_refs=observation_refs,
                layer_segment_refs=(
                    "annotation-layer-segment:"
                    + legacy.canonical_sha256(
                        {
                            "layer_ref": base_logical_layer.layer_ref,
                            "fibre_ref": fibre.fibre_ref,
                        }
                    ),
                    "annotation-layer-segment:"
                    + legacy.canonical_sha256(
                        {
                            "layer_ref": semantic_logical_layer.layer_ref,
                            "fibre_ref": fibre.fibre_ref,
                        }
                    ),
                ),
                relational_bundle_ref=bundle_ref,
                boundary_demand_refs=demand_refs,
            )
        )
    if projection_partition_persistence is not None:
        # Persistence is execution policy injected into the sole semantic
        # compiler. Partition rows are reusable metadata, never a document.
        projection_partition_persistence(tuple(row.to_dict() for row in partitions))
    projection_manifest = document_projection_join(
        partitions=partitions,
        logical_layers=(base_logical_layer, semantic_logical_layer),
        canonical_length=len(text),
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
            legacy.canonical_json(row) for row in unresolved_span_diagnostics
        ],
        "unresolved_span_diagnostic_summary": [
            legacy.canonical_json(row)
            for row in legacy.summarize_untyped_diagnostics(unresolved_span_diagnostics)
        ],
        "annotation_layer": _annotation_layer_records(layer),
        "parser_receipt": parser_receipt,
        "document_structural_carrier": parser_receipt.get(
            "document_structural_carrier"
        ),
        "cross_fibre_demands": cross_fibre_demands,
        "cross_fibre_fixed_point": cross_fibre_fixed_point,
        "annotation_graph": {
            "graph_ref": projection_manifest.graph_ref,
            "layer_refs": list(projection_manifest.logical_layer_refs),
        },
        "projection_partition_manifests": [row.to_dict() for row in partitions],
        "logical_layer_manifests": [
            base_logical_layer.to_dict(),
            semantic_logical_layer.to_dict(),
        ],
        "document_projection_manifest": projection_manifest.to_dict(),
        "semantic_annotation_layer": _annotation_layer_records(semantic_layer),
        "relational_bundle": legacy.canonical_json(relational_bundle),
        "semantic_reduction_declarations": [row.to_dict() for row in declarations],
        "compiler_declarations": [
            legacy.canonical_json(row) for row in legacy._compiler_declarations()
        ],
        "semantic_reduction_refs": list(semantic_output.declaration_refs),
        "semantic_reduction_constraints": [
            row.to_dict() for row in semantic_output.constraints
        ],
        "constraint_assessments": [row.to_dict() for row in constraint_assessments],
        "local_evidence": [row.to_dict() for row in local_evidence],
        "local_meet_plan": [legacy.canonical_json(row) for row in local_meet_plan],
        "pnf_graph": _pnf_graph_records(pnf_graph),
        "refined_pnf_graph": _pnf_graph_records(refined_pnf_graph),
        "resolution_demands": [legacy.canonical_json(row) for row in demands],
        "typed_meets": [row.to_dict() for row in typed_meets],
        "factor_refinements": [row.to_dict() for row in refinements],
        "streaming_semantic_build": streaming_build,
        "semantic_stage_timing": timings.to_dict(),
        "operational_compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
        "semantic_runtime_configuration": {
            "closure_workers": closure_workers,
            "owner_partitions": owner_partitions,
            "parser_workers": parser_workers,
            "parser_limit_chars": parser_limit_chars,
            "parser_target_chars": parser_target_chars,
            "parser_overlap_chars": parser_overlap_chars,
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
            "chunks_are_execution_partitions": True,
            "document_is_semantic_object": True,
            "cross_fibre_unresolved_demand_count": int(
                cross_fibre_fixed_point.get("unresolved_demand_count") or 0
            ),
        },
    }
    operational_artifacts = build_operational_reference_binding_artifacts(artifacts)
    resource_guard.checkpoint(
        stage="demand_derivation",
        current_kernel="artifact_projection",
        retained_indexes=len(operational_artifacts),
        reusable_partition_refs=tuple(row.partition_ref for row in partitions),
    )
    projected_artifacts, artifact_reader = project_artifacts(
        operational_artifacts,
        policy=artifact_projection_policy or ArtifactProjectionPolicy.production(),
    )
    resource_guard.checkpoint(
        stage="demand_derivation",
        current_kernel="artifact_projection_release",
        persisted_counts={
            key: int(value.get("record_count") or 0)
            for key, value in projected_artifacts.items()
            if isinstance(value, Mapping) and value.get("representation") == "manifest"
        },
        reusable_partition_refs=tuple(row.partition_ref for row in partitions),
    )
    return legacy.DocumentCompilation(
        document_ref=document_ref,
        content_sha256=content_sha256,
        media_type=media_type,
        artifacts=projected_artifacts,
        artifact_reader=artifact_reader,
    )


__all__ = [
    "OPERATIONAL_COMPILER_CONTRACT",
    "compile_document_operational",
]
