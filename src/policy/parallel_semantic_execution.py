"""Indexed, checkpointed, and audited intra-document semantic execution.

The canonical compiler remains the sole semantic authority.  This module installs
execution-only strategies: output-sensitive overlap indexes, immutable typing
leaf checkpoints, pure closure-receipt replay, kernel telemetry, and semantic
amplification receipts.
"""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from threading import Lock
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence, TypeVar

from src.policy.carriers.canonical import canonical_sha256
from src.runtime.execution_resource_ledger import (
    ExecutionResourceLedger,
    sample_process_resources,
)
from src.runtime.interval_overlap import IntervalRecord
from src.runtime.semantic_amplification import (
    candidate_set_report,
    closure_amplification_report,
    demand_report,
    meet_refinement_report,
)
from src.runtime.typing_hierarchy import (
    TYPING_EXECUTION_CONTRACT,
    TypingExecutionIdentity,
    execute_partitioned_overlap,
)


T = TypeVar("T")
_INSTALL_MARKER = "_parallel_semantic_execution_installed"
SEMANTIC_EXECUTION_SCHEMA_VERSION = "sensiblaw.semantic-execution-receipt.v1"
CLOSURE_REPLAY_CONTRACT = "closure-receipt-replay:v1"


def _integer_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


@dataclass
class SemanticExecutionContext:
    document_ref: str
    source_sha256: str
    parser_contract_ref: str
    build_key_sha256: str
    typing_workers: int
    leaf_capacity: int
    hierarchy_arity: int
    checkpoint_root: Path | None
    resource_ledger: ExecutionResourceLedger | None
    run_ref: str
    kernel_timeline: list[dict[str, Any]] = field(default_factory=list)
    typing_receipts: dict[str, dict[str, Any]] = field(default_factory=dict)
    closure_events: list[dict[str, Any]] = field(default_factory=list)
    closure_counters: Counter[str] = field(default_factory=Counter)
    amplification: dict[str, Any] = field(default_factory=dict)
    state: str = "running"
    error: dict[str, str] | None = None
    lock: Lock = field(default_factory=Lock, repr=False)

    @property
    def typing_identity(self) -> TypingExecutionIdentity:
        return TypingExecutionIdentity(
            document_ref=self.document_ref,
            source_sha256=self.source_sha256,
            parser_contract_ref=self.parser_contract_ref,
            build_key_sha256=self.build_key_sha256,
        )

    @property
    def typing_checkpoint_root(self) -> Path | None:
        if self.checkpoint_root is None:
            return None
        return self.checkpoint_root / "typing"

    @property
    def closure_checkpoint_root(self) -> Path | None:
        if self.checkpoint_root is None:
            return None
        return self.checkpoint_root / "closure-receipts"

    def sample(
        self,
        stage: str,
        *,
        phase: str,
        counts: Mapping[str, int] | None = None,
        details: Mapping[str, Any] | None = None,
        elapsed_ns: int | None = None,
    ) -> dict[str, Any]:
        detail = {
            **dict(details or {}),
            "counts": dict(counts or {}),
            **({"kernel_elapsed_ns": elapsed_ns} if elapsed_ns is not None else {}),
        }
        if self.resource_ledger is not None:
            resource_row = self.resource_ledger.sample(
                stage,
                phase=phase,
                details=detail,
            ).to_dict()
        else:
            resource_row = sample_process_resources()
        row = {
            "stage": stage,
            "phase": phase,
            "elapsed_ns": elapsed_ns,
            "counts": dict(sorted((counts or {}).items())),
            "details": dict(details or {}),
            "rss_bytes": int(resource_row.get("rss_bytes", 0)),
            "pss_bytes": int(resource_row.get("pss_bytes", 0)),
            "uss_bytes": int(resource_row.get("uss_bytes", 0)),
        }
        with self.lock:
            self.kernel_timeline.append(row)
        return row

    def closure_receipt_path(self, job_ref: str) -> Path | None:
        if self.closure_checkpoint_root is None:
            return None
        safe = "".join(
            character if character.isalnum() or character in "-_."
            else "_"
            for character in job_ref
        )
        return self.closure_checkpoint_root / f"{safe}.json"

    def write_receipts(self) -> None:
        if self.checkpoint_root is None:
            return
        closure = closure_amplification_report(self.closure_counters)
        receipt = {
            "schema_version": SEMANTIC_EXECUTION_SCHEMA_VERSION,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "parser_contract_ref": self.parser_contract_ref,
            "build_key_sha256": self.build_key_sha256,
            "typing_contract_ref": TYPING_EXECUTION_CONTRACT,
            "closure_replay_contract_ref": CLOSURE_REPLAY_CONTRACT,
            "configuration": {
                "typing_workers": self.typing_workers,
                "typing_leaf_capacity": self.leaf_capacity,
                "hierarchy_arity": self.hierarchy_arity,
            },
            "state": self.state,
            "error": self.error,
            "kernel_timeline": list(self.kernel_timeline),
            "typing_hierarchies": dict(sorted(self.typing_receipts.items())),
            "closure_audit": {
                "events": list(self.closure_events),
                **closure,
            },
            "amplification": dict(self.amplification),
            "semantic_authority": "one_document",
            "partition_semantic_effect": "none",
        }
        _atomic_write_json(
            self.checkpoint_root / "semantic-execution-receipt.json", receipt
        )
        _atomic_write_json(
            self.checkpoint_root / "semantic-amplification-report.json",
            {
                "schema_version": "sensiblaw.semantic-amplification-report.v1",
                "document_ref": self.document_ref,
                **dict(self.amplification),
                "closure": closure,
            },
        )


_CONTEXT: ContextVar[SemanticExecutionContext | None] = ContextVar(
    "sensiblaw_semantic_execution_context", default=None
)
_ACTIVE_CONTEXTS: dict[str, SemanticExecutionContext] = {}
_ACTIVE_LOCK = Lock()


def _context_for_document(document_ref: str) -> SemanticExecutionContext | None:
    with _ACTIVE_LOCK:
        return _ACTIVE_CONTEXTS.get(document_ref)


def _kernel_call(
    *,
    name: str,
    locality: str,
    input_counts: Mapping[str, int],
    function: Callable[[], T],
    output_counts: Callable[[T], Mapping[str, int]],
) -> T:
    context = _CONTEXT.get()
    started = monotonic_ns()
    if context is not None:
        context.sample(
            f"local_typing_diagnostics:{name}",
            phase="kernel_started",
            counts=input_counts,
            details={"locality": locality},
        )
    result = function()
    if context is not None:
        context.sample(
            f"local_typing_diagnostics:{name}",
            phase="kernel_completed",
            counts=output_counts(result),
            details={"locality": locality},
            elapsed_ns=monotonic_ns() - started,
        )
    return result


def indexed_atom_mention_refs(
    *,
    semantic_layer: Any,
    atom_span_refs: Mapping[str, str],
    mentions: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    context = _CONTEXT.get()
    spans_by_ref = {
        span.span_ref: span
        for span in semantic_layer.span_annotations
        if span.annotation_type == "semantic_atom"
    }
    atoms = tuple(
        IntervalRecord(
            str(atom_ref),
            int(spans_by_ref[span_ref].start_token),
            int(spans_by_ref[span_ref].end_token),
        )
        for atom_ref, span_ref in sorted(atom_span_refs.items())
        if span_ref in spans_by_ref
    )
    mention_rows = tuple(
        IntervalRecord(
            str(row["mention_ref"]),
            int(row["start_token"]),
            int(row["end_token"]),
        )
        for row in mentions
    )
    if context is None:
        identity = TypingExecutionIdentity(
            document_ref=f"typing-document:{canonical_sha256(semantic_layer.layer_ref)}",
            source_sha256=str(semantic_layer.text_sha256),
            parser_contract_ref=str(semantic_layer.tokenizer_ref),
        )
        rows, _receipt = execute_partitioned_overlap(
            operation="atom-mention-matching",
            identity=identity,
            left_records=atoms,
            right_records=mention_rows,
            workers=1,
        )
        return rows

    def observe(payload: Mapping[str, Any]) -> None:
        context.sample(
            "local_typing_diagnostics:atom_mention_matching",
            phase="typing_leaf_completed",
            counts={
                "leaf_input_rows": int(payload["input_row_count"]),
                "leaf_matches": int(payload["record_count"]),
            },
            details=dict(payload),
            elapsed_ns=int(payload["elapsed_ns"]),
        )

    started = monotonic_ns()
    rows, receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=context.typing_identity,
        left_records=atoms,
        right_records=mention_rows,
        workers=context.typing_workers,
        leaf_capacity=context.leaf_capacity,
        arity=context.hierarchy_arity,
        checkpoint_root=context.typing_checkpoint_root,
        stop_after_new_leaves=_integer_env(
            "SENSIBLAW_TYPING_STOP_AFTER_LEAVES", 0, minimum=0
        ),
        observer=observe,
    )
    context.typing_receipts["atom-mention-matching"] = receipt
    context.sample(
        "local_typing_diagnostics:atom_mention_matching",
        phase="kernel_completed",
        counts={
            "atoms": len(atoms),
            "mentions": len(mention_rows),
            "matched_atoms": len(rows),
            "actual_matches": sum(len(value) for value in rows.values()),
        },
        details={
            "complexity_target": "O(A + M + K)",
            "root_graph_ref": receipt["root_graph_ref"],
            "descendant_bytes_reconstructed": 0,
        },
        elapsed_ns=monotonic_ns() - started,
    )
    return rows


def indexed_parser_observation_refs_by_mention(
    *,
    semantic_layer: Any,
    mentions: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    context = _CONTEXT.get()
    mention_rows = tuple(
        IntervalRecord(
            str(row["mention_ref"]),
            int(row["start_token"]),
            int(row["end_token"]),
        )
        for row in mentions
    )
    parser_rows = tuple(
        IntervalRecord(
            str(span.span_ref),
            int(span.start_token),
            int(span.end_token),
        )
        for span in semantic_layer.span_annotations
        if span.annotation_type == "parser_token"
    )
    identity = (
        context.typing_identity
        if context is not None
        else TypingExecutionIdentity(
            document_ref=f"typing-document:{canonical_sha256(semantic_layer.layer_ref)}",
            source_sha256=str(semantic_layer.text_sha256),
            parser_contract_ref=str(semantic_layer.tokenizer_ref),
        )
    )

    def observe(payload: Mapping[str, Any]) -> None:
        if context is not None:
            context.sample(
                "local_typing_diagnostics:parser_observation_matching",
                phase="typing_leaf_completed",
                counts={
                    "leaf_input_rows": int(payload["input_row_count"]),
                    "leaf_matches": int(payload["record_count"]),
                },
                details=dict(payload),
                elapsed_ns=int(payload["elapsed_ns"]),
            )

    started = monotonic_ns()
    rows, receipt = execute_partitioned_overlap(
        operation="mention-parser-observation-matching",
        identity=identity,
        left_records=mention_rows,
        right_records=parser_rows,
        workers=context.typing_workers if context is not None else 1,
        leaf_capacity=context.leaf_capacity if context is not None else 4096,
        arity=context.hierarchy_arity if context is not None else 4,
        checkpoint_root=(
            context.typing_checkpoint_root if context is not None else None
        ),
        observer=observe,
    )
    if context is not None:
        context.typing_receipts["mention-parser-observation-matching"] = receipt
        context.sample(
            "local_typing_diagnostics:parser_observation_matching",
            phase="kernel_completed",
            counts={
                "mentions": len(mention_rows),
                "parser_spans": len(parser_rows),
                "matched_mentions": len(rows),
                "actual_matches": sum(len(value) for value in rows.values()),
            },
            details={
                "complexity_target": "O(M + P + K)",
                "root_graph_ref": receipt["root_graph_ref"],
                "descendant_bytes_reconstructed": 0,
            },
            elapsed_ns=monotonic_ns() - started,
        )
    return rows


def _factor_proposal_from_row(row: Mapping[str, Any]) -> Any:
    from src.pnf.factor_proposals import FactorProposal

    names = (
        "document_ref",
        "source_revision_ref",
        "factor_type_ref",
        "source_span_refs",
        "input_observation_refs",
        "dependency_factor_refs",
        "structural_signature",
        "role_bindings",
        "qualifier_state",
        "producer_contract",
        "declaration_revision",
        "candidate_payload",
        "residuals",
        "scope_ref",
        "statement_role",
        "coordinate_kind",
        "semantic_coordinate_ref",
        "fibre_kind",
        "derivation_role",
        "producer_scope",
        "operation_contract",
        "ontology_axis_refs",
        "transport_refs",
        "support_state",
        "confidence",
        "assumptions",
        "coverage_requirements",
        "execution_metadata",
    )
    values = {name: row[name] for name in names if name in row}
    for name in (
        "source_span_refs",
        "input_observation_refs",
        "dependency_factor_refs",
        "residuals",
        "ontology_axis_refs",
        "transport_refs",
        "assumptions",
        "coverage_requirements",
    ):
        if name in values:
            values[name] = tuple(values[name] or ())
    return FactorProposal(**values)


def _solver_receipt_from_row(row: Mapping[str, Any]) -> Any:
    from src.pnf.streaming_fixed_point import OwnerKey, SolverReceipt

    receipt = SolverReceipt(
        job_ref=str(row["job_ref"]),
        owner_key=OwnerKey(**dict(row["owner_key"])),
        input_revision=int(row["input_revision"]),
        input_refs=tuple(row.get("input_refs") or ()),
        rule_set_revision=str(row["rule_set_revision"]),
        proposals=tuple(
            _factor_proposal_from_row(value)
            for value in row.get("proposals") or ()
            if isinstance(value, Mapping)
        ),
        residuals=tuple(row.get("residuals") or ()),
        assumptions=tuple(row.get("assumptions") or ()),
        coverage_requirements=tuple(row.get("coverage_requirements") or ()),
        metrics=dict(row.get("metrics") or {}),
        backend_ref=str(row.get("backend_ref") or "python-worklist:v0_1"),
    )
    if row.get("receipt_ref") and receipt.receipt_ref != row["receipt_ref"]:
        raise ValueError("cached solver receipt identity mismatch")
    return receipt


def _build_context(
    args: Sequence[Any], kwargs: Mapping[str, Any]
) -> SemanticExecutionContext:
    document_input = args[0] if args else kwargs.get("document_input")
    compiler_context = args[1] if len(args) > 1 else kwargs.get("compiler_context")
    if not isinstance(document_input, Mapping):
        raise ValueError("operational compile requires document_input")
    document_ref = str(document_input.get("document_ref") or "")
    source_sha256 = str(document_input.get("content_sha256") or "")
    parser_contract = str(
        getattr(compiler_context, "annotation_backend_ref", "unknown")
    )
    closure_workers = int(kwargs.get("closure_workers", 2))
    parser_checkpoint = kwargs.get("parser_checkpoint_dir")
    root_raw = os.environ.get("SENSIBLAW_SEMANTIC_CHECKPOINT_DIR")
    if root_raw:
        checkpoint_root: Path | None = Path(root_raw)
    elif parser_checkpoint:
        checkpoint_root = Path(str(parser_checkpoint)).parent / "semantic_checkpoints"
    else:
        checkpoint_root = None
    build_key = canonical_sha256(
        {
            "document_ref": document_ref,
            "source_sha256": source_sha256,
            "parser_contract_ref": parser_contract,
            "typing_contract_ref": TYPING_EXECUTION_CONTRACT,
        }
    )
    return SemanticExecutionContext(
        document_ref=document_ref,
        source_sha256=source_sha256,
        parser_contract_ref=parser_contract,
        build_key_sha256=build_key,
        typing_workers=_integer_env(
            "SENSIBLAW_TYPING_WORKERS", max(1, closure_workers)
        ),
        leaf_capacity=_integer_env("SENSIBLAW_TYPING_LEAF_CAPACITY", 4096),
        hierarchy_arity=_integer_env(
            "SENSIBLAW_TYPING_HIERARCHY_ARITY", 4, minimum=2
        ),
        checkpoint_root=checkpoint_root,
        resource_ledger=kwargs.get("resource_ledger"),
        run_ref="semantic-execution:"
        + canonical_sha256(
            {
                "document_ref": document_ref,
                "source_sha256": source_sha256,
                "parser_contract_ref": parser_contract,
                "typing_contract_ref": TYPING_EXECUTION_CONTRACT,
            }
        ),
    )


def install_parallel_semantic_execution() -> bool:
    """Install indexed typing, closure replay, and amplification receipts."""

    from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
    from src.pnf.streaming_fixed_point import PythonClosureExecutor
    from src.policy import corpus_compilation as legacy
    from src.policy import operational_corpus_compilation as operational

    if getattr(operational, _INSTALL_MARKER, False):
        return False

    if not hasattr(legacy, "_serial_atom_mention_refs"):
        legacy._serial_atom_mention_refs = legacy._atom_mention_refs
    if not hasattr(legacy, "_serial_parser_observation_refs_by_mention"):
        legacy._serial_parser_observation_refs_by_mention = (
            legacy._parser_observation_refs_by_mention
        )
    legacy._atom_mention_refs = indexed_atom_mention_refs
    legacy._parser_observation_refs_by_mention = (
        indexed_parser_observation_refs_by_mention
    )

    original_derive = legacy.derive_relational_type_hypotheses
    original_build_typing = legacy.build_local_typing_carrier
    original_diagnose = legacy.diagnose_untyped_mentions
    original_summarize = legacy.summarize_untyped_diagnostics
    original_reduce_bundle = legacy.reduce_relational_bundle
    original_build_graph = legacy._build_pnf_graph
    original_meets = legacy._local_meets_and_refinements
    original_demands = legacy.derive_resolution_demands
    original_binding = operational.build_operational_reference_binding_artifacts
    original_compile = operational.compile_document_operational
    original_streaming = operational._streaming_semantic_build
    original_reduce_dirty = BoundedStreamingSemanticOwner.reduce_dirty_groups
    original_execute = PythonClosureExecutor.execute

    def derive_wrapper(*args: Any, **kwargs: Any) -> Any:
        bundle = kwargs.get("bundle") or (args[0] if args else {})
        atom_mentions = kwargs.get("atom_mention_refs") or {}
        return _kernel_call(
            name="structural_hypothesis_derivation",
            locality="document_global_join",
            input_counts={
                "atoms": len((bundle or {}).get("atoms") or ()),
                "relations": len((bundle or {}).get("relations") or ()),
                "atom_mention_keys": len(atom_mentions),
            },
            function=lambda: original_derive(*args, **kwargs),
            output_counts=lambda value: {"structural_hypotheses": len(value)},
        )

    def build_typing_wrapper(*args: Any, **kwargs: Any) -> Any:
        return _kernel_call(
            name="local_type_carrier_build",
            locality="document_global_join",
            input_counts={
                "mentions": len(kwargs.get("mentions") or ()),
                "forms": len(kwargs.get("forms") or ()),
                "structural_hypotheses": len(
                    kwargs.get("structural_hypotheses") or ()
                ),
            },
            function=lambda: original_build_typing(*args, **kwargs),
            output_counts=lambda value: {
                "local_type_alternatives": len(
                    (value or {}).get("local_type_alternatives") or ()
                )
            },
        )

    def diagnose_wrapper(*args: Any, **kwargs: Any) -> Any:
        return _kernel_call(
            name="untyped_diagnostic_generation",
            locality="document_global_join",
            input_counts={"mentions": len(kwargs.get("mentions") or ())},
            function=lambda: original_diagnose(*args, **kwargs),
            output_counts=lambda value: {"untyped_diagnostics": len(value)},
        )

    def summarize_wrapper(*args: Any, **kwargs: Any) -> Any:
        diagnostics = args[0] if args else kwargs.get("diagnostics") or ()
        return _kernel_call(
            name="diagnostic_summary",
            locality="document_global",
            input_counts={"diagnostics": len(diagnostics)},
            function=lambda: original_summarize(*args, **kwargs),
            output_counts=lambda value: {"diagnostic_summaries": len(value)},
        )

    def reduce_bundle_wrapper(*args: Any, **kwargs: Any) -> Any:
        bundle = kwargs.get("bundle") or {}
        return _kernel_call(
            name="base_relational_reduction",
            locality="document_global_join",
            input_counts={
                "atoms": len(bundle.get("atoms") or ()),
                "relations": len(bundle.get("relations") or ()),
            },
            function=lambda: original_reduce_bundle(*args, **kwargs),
            output_counts=lambda value: {
                "factors": len(value.factors),
                "constraints": len(value.constraints),
                "relation_refs": len(value.relation_refs),
            },
        )

    def build_graph_wrapper(*args: Any, **kwargs: Any) -> Any:
        return _kernel_call(
            name="pnf_graph_materialization",
            locality="document_root",
            input_counts={
                "mentions": len(kwargs.get("mentions") or ()),
                "local_types": len(kwargs.get("local_types") or ()),
                "semantic_factors": len(kwargs.get("semantic_factors") or ()),
            },
            function=lambda: original_build_graph(*args, **kwargs),
            output_counts=lambda value: {
                "pnf_factors": len(value.factors),
                "pnf_constraints": len(value.constraints),
            },
        )

    def meets_wrapper(*args: Any, **kwargs: Any) -> Any:
        graph = kwargs.get("graph")
        result = _kernel_call(
            name="meet_refinement_generation",
            locality="document_root",
            input_counts={
                "factors": len(getattr(graph, "factors", ()) or ()),
                "evidence": len(kwargs.get("evidence") or ()),
                "constraint_assessments": len(
                    kwargs.get("constraint_assessments") or ()
                ),
            },
            function=lambda: original_meets(*args, **kwargs),
            output_counts=lambda value: {
                "typed_meets": len(value[1]),
                "refinements": len(value[2]),
            },
        )
        context = _CONTEXT.get()
        if context is not None:
            context.amplification.update(
                meet_refinement_report(result[1], result[2])
            )
        return result

    def demands_wrapper(*args: Any, **kwargs: Any) -> Any:
        graph = args[0] if args else kwargs.get("graph")
        result = _kernel_call(
            name="demand_derivation",
            locality="document_root",
            input_counts={"factors": len(getattr(graph, "factors", ()) or ())},
            function=lambda: original_demands(*args, **kwargs),
            output_counts=lambda value: {"demands": len(value)},
        )
        context = _CONTEXT.get()
        if context is not None:
            context.amplification.update(demand_report(result))
        return result

    def binding_wrapper(artifacts: Mapping[str, Any]) -> dict[str, Any]:
        result = original_binding(artifacts)
        context = _CONTEXT.get()
        if context is not None:
            context.amplification.update(candidate_set_report(result))
        return result

    def reduce_dirty_wrapper(self: Any) -> Any:
        context = _CONTEXT.get()
        dirty = tuple(sorted(self._dirty_groups))
        proposals_examined = sum(
            len(self._proposals_by_owner.get(key, {})) for key in dirty
        )
        settled_rescans = sum(1 for key in dirty if key in self._reductions)
        started = monotonic_ns()
        result = original_reduce_dirty(self)
        if context is not None:
            with context.lock:
                context.closure_counters["reduction_batches"] += 1
                context.closure_counters["dirty_groups_reduced"] += len(dirty)
                context.closure_counters["proposals_examined"] += proposals_examined
                context.closure_counters["factor_scans"] += proposals_examined
                context.closure_counters["settled_groups_rescanned"] += settled_rescans
                context.closure_counters["changed_factors"] += len(
                    result.changed_factor_refs
                )
                context.closure_counters["revisions_introduced"] += max(
                    0, result.resulting_revision - result.prior_revision
                )
            context.sample(
                "streaming_closure:dirty_group_reduction",
                phase="closure_batch",
                counts={
                    "dirty_groups": len(dirty),
                    "proposals_examined": proposals_examined,
                    "settled_groups_rescanned": settled_rescans,
                    "changed_factors": len(result.changed_factor_refs),
                },
                elapsed_ns=monotonic_ns() - started,
            )
        return result

    def execute_wrapper(self: Any, job: Any) -> Any:
        context = _context_for_document(job.owner_key.document_ref)
        if context is None:
            return original_execute(self, job)
        path = context.closure_receipt_path(job.job_ref)
        if path is not None and path.exists():
            payload = _read_json(path)
            if payload is not None:
                receipt = _solver_receipt_from_row(payload)
                with context.lock:
                    context.closure_counters["receipts_reused"] += 1
                return receipt
        receipt = original_execute(self, job)
        if path is not None:
            _atomic_write_json(path, receipt.to_dict())
        with context.lock:
            context.closure_counters["receipts_computed"] += 1
            context.closure_counters["proposals_emitted"] += len(receipt.proposals)
            context.closure_counters["dependency_fanout"] += sum(
                len(proposal.dependency_factor_refs)
                for proposal in receipt.proposals
            )
        stop_after = _integer_env(
            "SENSIBLAW_CLOSURE_STOP_AFTER_RECEIPTS", 0, minimum=0
        )
        if (
            stop_after
            and context.closure_counters["receipts_computed"] >= stop_after
        ):
            raise RuntimeError(
                f"stopped after {stop_after} checkpointed closure receipts"
            )
        return receipt

    def streaming_wrapper(*args: Any, **kwargs: Any) -> Any:
        context = _CONTEXT.get()
        observer = kwargs.get("progress_observer")
        last_jobs = -1
        last_kernel = ""

        def audited(payload: Mapping[str, Any]) -> None:
            nonlocal last_jobs, last_kernel
            if observer is not None:
                observer(payload)
            if context is None:
                return
            row = dict(payload)
            jobs = int(row.get("jobs_completed") or 0)
            kernel = str(row.get("current_kernel") or "streaming_closure")
            if kernel != last_kernel or jobs == 0 or jobs - last_jobs >= 32:
                resources = sample_process_resources()
                event = {
                    **row,
                    "rss_bytes": int(resources["rss_bytes"]),
                    "pss_bytes": int(resources["pss_bytes"]),
                    "uss_bytes": int(resources["uss_bytes"]),
                }
                with context.lock:
                    context.closure_events.append(event)
                last_jobs = jobs
                last_kernel = kernel

        kwargs["progress_observer"] = audited
        started = monotonic_ns()
        result = original_streaming(*args, **kwargs)
        if context is not None:
            _build, metrics = result
            with context.lock:
                context.closure_counters["jobs_completed"] = int(
                    metrics.get("closure_job_count") or 0
                )
                context.closure_counters["proposals_emitted"] = max(
                    context.closure_counters["proposals_emitted"],
                    int(metrics.get("derived_proposal_count") or 0),
                )
                context.closure_counters["materialized_factors"] = int(
                    metrics.get("materialized_factor_count") or 0
                )
            context.sample(
                "streaming_closure:fixed_point",
                phase="kernel_completed",
                counts={
                    "jobs_completed": context.closure_counters["jobs_completed"],
                    "proposals_examined": context.closure_counters[
                        "proposals_examined"
                    ],
                    "proposals_emitted": context.closure_counters[
                        "proposals_emitted"
                    ],
                    "changed_factors": context.closure_counters["changed_factors"],
                },
                elapsed_ns=monotonic_ns() - started,
            )
        return result

    def compile_wrapper(*args: Any, **kwargs: Any) -> Any:
        context = _build_context(args, kwargs)
        token = _CONTEXT.set(context)
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS[context.document_ref] = context
        try:
            result = original_compile(*args, **kwargs)
            context.state = "completed"
            artifacts = getattr(result, "artifacts", {}) or {}
            context.amplification["identity_receipt"] = {
                "annotation_graph_ref": str(
                    (artifacts.get("annotation_graph") or {}).get("graph_ref") or ""
                ),
                "logical_layer_refs": [
                    str(row.get("layer_ref") or "")
                    for row in artifacts.get("logical_layer_manifests") or ()
                    if isinstance(row, Mapping)
                ],
                "document_projection_manifest_ref": str(
                    (artifacts.get("document_projection_manifest") or {}).get(
                        "manifest_ref"
                    )
                    or ""
                ),
                "manifest_descriptors": {
                    key: {
                        "root_ref": value.get("root_ref"),
                        "ordered_digest": value.get("ordered_digest"),
                        "record_count": value.get("record_count"),
                    }
                    for key, value in artifacts.items()
                    if isinstance(value, Mapping)
                    and value.get("representation") == "manifest"
                },
            }
            return result
        except Exception as error:
            context.state = "failed"
            context.error = {
                "type": type(error).__name__,
                "message": str(error),
            }
            raise
        finally:
            context.write_receipts()
            with _ACTIVE_LOCK:
                _ACTIVE_CONTEXTS.pop(context.document_ref, None)
            _CONTEXT.reset(token)

    legacy.derive_relational_type_hypotheses = derive_wrapper
    legacy.build_local_typing_carrier = build_typing_wrapper
    legacy.diagnose_untyped_mentions = diagnose_wrapper
    legacy.summarize_untyped_diagnostics = summarize_wrapper
    legacy.reduce_relational_bundle = reduce_bundle_wrapper
    legacy._build_pnf_graph = build_graph_wrapper
    legacy._local_meets_and_refinements = meets_wrapper
    legacy.derive_resolution_demands = demands_wrapper
    operational.build_operational_reference_binding_artifacts = binding_wrapper
    BoundedStreamingSemanticOwner.reduce_dirty_groups = reduce_dirty_wrapper
    PythonClosureExecutor.execute = execute_wrapper
    operational._streaming_semantic_build = streaming_wrapper
    operational.compile_document_operational = compile_wrapper
    operational._canonical_compile_document_operational = original_compile
    operational._bounded_streaming_semantic_build = original_streaming
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = [
    "CLOSURE_REPLAY_CONTRACT",
    "SEMANTIC_EXECUTION_SCHEMA_VERSION",
    "SemanticExecutionContext",
    "indexed_atom_mention_refs",
    "indexed_parser_observation_refs_by_mention",
    "install_parallel_semantic_execution",
]
