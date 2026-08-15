"""Indexed, checkpointed, and audited intra-document semantic execution.

The canonical compiler remains the sole semantic authority.  This module installs
execution-only strategies: output-sensitive overlap indexes, immutable typing
leaf checkpoints, pure closure-receipt replay, kernel telemetry, and semantic
amplification receipts.
"""

from __future__ import annotations

from collections import Counter
from concurrent.futures import FIRST_COMPLETED, wait
from contextvars import ContextVar
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from threading import Lock
from time import monotonic_ns
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence, TypeVar

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
CLOSURE_ACTIVATION_LEAF_SCHEMA_VERSION = "sensiblaw.closure-activation-leaf.v1"
CLOSURE_ACTIVATION_CONTRACT = "closure-activation-leaves:v1"
CLOSURE_HANDOFF_SCHEMA_VERSION = "sensiblaw.closure-handoff-state.v2"
CLOSURE_HANDOFF_CONTRACT = "closure-owner-replay:v2"
CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION = "sensiblaw.closure-replay-artifact.v1"


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
    closure_activation_leaf_size: int = 512
    kernel_timeline: list[dict[str, Any]] = field(default_factory=list)
    typing_receipts: dict[str, dict[str, Any]] = field(default_factory=dict)
    closure_events: list[dict[str, Any]] = field(default_factory=list)
    closure_counters: Counter[str] = field(default_factory=Counter)
    closure_activation: dict[str, Any] = field(default_factory=dict)
    closure_activation_completed_ns: int | None = field(default=None, repr=False)
    amplification: dict[str, Any] = field(default_factory=dict)
    state: str = "running"
    error: dict[str, str] | None = None
    reconstructing_owner: bool = field(default=False, repr=False)
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

    @property
    def closure_activation_checkpoint_root(self) -> Path | None:
        if self.checkpoint_root is None:
            return None
        return self.checkpoint_root / "closure-activation"

    @property
    def closure_handoff_checkpoint_path(self) -> Path | None:
        if self.closure_activation_checkpoint_root is None:
            return None
        return (
            self.closure_activation_checkpoint_root
            / f"handoff-{self.build_key_sha256}.json"
        )

    @property
    def closure_replay_artifact_root(self) -> Path | None:
        if self.closure_activation_checkpoint_root is None:
            return None
        return self.closure_activation_checkpoint_root / "replay-artifacts"

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
            character if character.isalnum() or character in "-_." else "_"
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
            "closure_activation_contract_ref": CLOSURE_ACTIVATION_CONTRACT,
            "configuration": {
                "typing_workers": self.typing_workers,
                "typing_leaf_capacity": self.leaf_capacity,
                "hierarchy_arity": self.hierarchy_arity,
                "closure_activation_leaf_size": self.closure_activation_leaf_size,
            },
            "state": self.state,
            "error": self.error,
            "kernel_timeline": list(self.kernel_timeline),
            "typing_hierarchies": dict(sorted(self.typing_receipts.items())),
            "closure_audit": {
                "events": list(self.closure_events),
                "activation": dict(self.closure_activation),
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
        hierarchy_arity=_integer_env("SENSIBLAW_TYPING_HIERARCHY_ARITY", 4, minimum=2),
        closure_activation_leaf_size=_integer_env(
            "SENSIBLAW_CLOSURE_ACTIVATION_LEAF_SIZE", 512
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


def _closure_activation_leaf_path(root: Path | None, leaf_ref: str) -> Path | None:
    if root is None:
        return None
    return root / f"{leaf_ref.replace(':', '_')}.json"


def _handoff_identity(context: SemanticExecutionContext) -> dict[str, str]:
    """Return the complete compatibility identity for closure replay state.

    Replay artifacts are immutable and content addressed.  Their namespace must
    include the contract that defines how the content is interpreted; otherwise
    a pre-v2 artifact can share a value-derived reference with a v2 artifact.
    """

    return {
        "document_ref": context.document_ref,
        "source_sha256": context.source_sha256,
        "parser_contract_ref": context.parser_contract_ref,
        "build_key_sha256": context.build_key_sha256,
        "handoff_schema_version": CLOSURE_HANDOFF_SCHEMA_VERSION,
        "handoff_contract_ref": CLOSURE_HANDOFF_CONTRACT,
        "artifact_schema_version": CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION,
    }


def _write_closure_handoff_checkpoint(context: SemanticExecutionContext) -> None:
    """Persist a self-verifying replay contract, never Python owner internals."""

    path = context.closure_handoff_checkpoint_path
    if path is None or context.reconstructing_owner:
        return
    activation = context.closure_activation
    payload: dict[str, Any] = {
        "schema_version": CLOSURE_HANDOFF_SCHEMA_VERSION,
        "contract_ref": CLOSURE_HANDOFF_CONTRACT,
        **_handoff_identity(context),
        "next_leaf_ordinal": int(activation.get("next_leaf_ordinal") or 0),
        "completed_leaf_refs": list(activation.get("completed_leaf_refs") or ()),
        "buffered_leaf_refs": list(activation.get("buffered_leaf_refs") or ()),
        "admitted_leaf_refs": list(activation.get("admitted_leaf_refs") or ()),
        "admitted_batch_refs": list(activation.get("admitted_batch_refs") or ()),
        "recorded_delta_refs": list(activation.get("recorded_delta_refs") or ()),
        "delta_artifact_refs": list(activation.get("delta_artifact_refs") or ()),
        "proposal_batch_artifact_refs": list(
            activation.get("proposal_batch_artifact_refs") or ()
        ),
        "receipt_artifact_refs": list(activation.get("receipt_artifact_refs") or ()),
        "reduction_artifact_refs": list(
            activation.get("reduction_artifact_refs") or ()
        ),
        "replay_events": list(activation.get("replay_events") or ()),
        "current_owner_revision": int(activation.get("current_owner_revision") or 0),
        "completed_reduction_key_refs": list(
            activation.get("completed_reduction_key_refs") or ()
        ),
        "unresolved_frontier_refs": list(
            activation.get("unresolved_frontier_refs") or ()
        ),
    }
    payload["checkpoint_ref"] = "closure-handoff:" + canonical_sha256(payload)
    _atomic_write_json(path, payload)


def _replay_artifact_path(
    context: SemanticExecutionContext, artifact_ref: str
) -> Path | None:
    root = context.closure_replay_artifact_root
    if root is None:
        return None
    safe = "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in artifact_ref
    )
    return root / f"{safe}.json"


def _write_replay_artifact(
    context: SemanticExecutionContext,
    *,
    artifact_kind: str,
    value: Any,
) -> str:
    identity = {
        "artifact_kind": artifact_kind,
        "owner_identity": _handoff_identity(context),
        "value_digest": canonical_sha256(value),
    }
    artifact_ref = "closure-replay:" + canonical_sha256(identity)
    payload = {
        "schema_version": CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION,
        "contract_ref": CLOSURE_HANDOFF_CONTRACT,
        "artifact_ref": artifact_ref,
        **identity,
        "value": value,
    }
    path = _replay_artifact_path(context, artifact_ref)
    if path is not None:
        existing = _read_json(path) if path.exists() else None
        if existing is not None and (
            existing.get("schema_version") != CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION
            or existing.get("contract_ref") != CLOSURE_HANDOFF_CONTRACT
            or existing.get("artifact_ref") != artifact_ref
            or existing.get("artifact_kind") != artifact_kind
            or existing.get("owner_identity") != _handoff_identity(context)
            or existing.get("value_digest") != identity["value_digest"]
            or canonical_sha256(existing.get("value")) != identity["value_digest"]
        ):
            raise ValueError("closure replay artifact identity collision")
        if existing is None:
            _atomic_write_json(path, payload)
    return artifact_ref


def _read_replay_artifact(
    context: SemanticExecutionContext,
    *,
    artifact_ref: str,
    artifact_kind: str,
) -> Any:
    if artifact_kind == "solver_receipt" and artifact_ref.startswith(
        "closure-receipt-artifact:"
    ):
        job_ref = "semantic-job:" + artifact_ref.split(":", maxsplit=1)[1]
        path = context.closure_receipt_path(job_ref)
        if path is None or not path.exists():
            raise ValueError(f"checkpointed solver receipt is missing: {job_ref}")
        value = _read_json(path)
        if value is None:
            raise ValueError(f"checkpointed solver receipt is corrupt: {job_ref}")
        receipt = _solver_receipt_from_row(value)
        if receipt.job_ref != job_ref:
            raise ValueError("checkpointed solver receipt job identity mismatch")
        return value
    path = _replay_artifact_path(context, artifact_ref)
    if path is None or not path.exists():
        raise ValueError(f"closure replay artifact is missing: {artifact_ref}")
    payload = _read_json(path)
    if (
        payload is None
        or payload.get("schema_version") != CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION
        or payload.get("contract_ref") != CLOSURE_HANDOFF_CONTRACT
        or payload.get("artifact_ref") != artifact_ref
        or payload.get("artifact_kind") != artifact_kind
        or payload.get("owner_identity") != _handoff_identity(context)
        or canonical_sha256(payload.get("value")) != payload.get("value_digest")
    ):
        raise ValueError(f"closure replay artifact is corrupt: {artifact_ref}")
    identity = {
        "artifact_kind": artifact_kind,
        "owner_identity": _handoff_identity(context),
        "value_digest": payload["value_digest"],
    }
    if "closure-replay:" + canonical_sha256(identity) != artifact_ref:
        raise ValueError(f"closure replay artifact reference mismatch: {artifact_ref}")
    return payload["value"]


def _append_replay_event(
    context: SemanticExecutionContext,
    *,
    artifact_kind: str,
    artifact_ref: str,
) -> None:
    if context.reconstructing_owner:
        return
    activation = context.closure_activation
    list_key = {
        "observation_delta": "delta_artifact_refs",
        "observation_delta_batch": "delta_artifact_refs",
        "proposal_batch": "proposal_batch_artifact_refs",
        "solver_receipt": "receipt_artifact_refs",
        "dirty_reduction": "reduction_artifact_refs",
    }[artifact_kind]
    refs = list(activation.get(list_key) or ())
    refs.append(artifact_ref)
    activation[list_key] = tuple(refs)
    events = list(activation.get("replay_events") or ())
    event = {"artifact_kind": artifact_kind, "artifact_ref": artifact_ref}
    events.append(event)
    activation["replay_events"] = tuple(events)


def _observation_delta_from_row(row: Mapping[str, Any]) -> Any:
    from src.pnf.streaming_fixed_point import ObservationDelta

    delta = ObservationDelta(
        document_ref=str(row["document_ref"]),
        batch_ref=str(row["batch_ref"]),
        scope_ref=str(row["scope_ref"]),
        sequence_no=int(row["sequence_no"]),
        parser_contract=str(row["parser_contract"]),
        observation_refs=tuple(row.get("observation_refs") or ()),
        observations=tuple(dict(value) for value in row.get("observations") or ()),
        token_start=int(row["token_start"]),
        token_end=int(row["token_end"]),
        char_start=int(row["char_start"]),
        char_end=int(row["char_end"]),
        token_count=int(row["token_count"]),
        coverage_barrier=str(row.get("coverage_barrier") or "sentence"),
        coverage_complete=bool(row.get("coverage_complete")),
    )
    if row.get("delta_ref") != delta.delta_ref:
        raise ValueError("checkpointed observation delta identity mismatch")
    return delta


class ClosureOwnerReplayContract:
    """Append-only owner event log and canonical fresh-owner reconstruction."""

    def __init__(self, context: SemanticExecutionContext):
        self.context = context
        self._checkpoint_calls = 0
        self.checkpoint = self._load_checkpoint()

    def _load_checkpoint(self) -> dict[str, Any] | None:
        path = self.context.closure_handoff_checkpoint_path
        if path is None or not path.exists():
            return None
        payload = _read_json(path)
        if payload is None:
            return None
        checkpoint_ref = payload.pop("checkpoint_ref", None)
        expected_ref = "closure-handoff:" + canonical_sha256(payload)
        payload["checkpoint_ref"] = checkpoint_ref
        if (
            payload.get("schema_version") != CLOSURE_HANDOFF_SCHEMA_VERSION
            or payload.get("contract_ref") != CLOSURE_HANDOFF_CONTRACT
            or any(
                payload.get(key) != value
                for key, value in _handoff_identity(self.context).items()
            )
            or checkpoint_ref != expected_ref
        ):
            return None
        events = payload.get("replay_events")
        if not isinstance(events, list) or any(
            not isinstance(event, Mapping)
            or event.get("artifact_kind")
            not in {
                "observation_delta",
                "observation_delta_batch",
                "proposal_batch",
                "solver_receipt",
                "dirty_reduction",
            }
            or not event.get("artifact_ref")
            for event in events
        ):
            return None
        expected_by_kind = {
            "proposal_batch": list(payload.get("proposal_batch_artifact_refs") or ()),
            "solver_receipt": list(payload.get("receipt_artifact_refs") or ()),
            "dirty_reduction": list(payload.get("reduction_artifact_refs") or ()),
        }
        actual_by_kind = {
            kind: [
                str(event["artifact_ref"])
                for event in events
                if event["artifact_kind"] == kind
            ]
            for kind in expected_by_kind
        }
        delta_events = [
            str(event["artifact_ref"])
            for event in events
            if event["artifact_kind"]
            in {"observation_delta", "observation_delta_batch"}
        ]
        if delta_events != list(payload.get("delta_artifact_refs") or ()):
            return None
        if actual_by_kind != expected_by_kind:
            return None
        self.context.closure_activation.update(
            {
                key: tuple(value) if isinstance(value, list) else value
                for key, value in payload.items()
                if key not in _handoff_identity(self.context)
            }
        )
        return payload

    @property
    def available(self) -> bool:
        return self.checkpoint is not None and bool(
            self.checkpoint.get("replay_events")
        )

    def reconstruct(self, owner: Any) -> None:
        if not self.available:
            return
        checkpoint = self.checkpoint or {}
        reconstructed = Counter()
        started = monotonic_ns()
        self.context.reconstructing_owner = True
        try:
            for event in checkpoint["replay_events"]:
                kind = str(event["artifact_kind"])
                artifact_ref = str(event["artifact_ref"])
                value = _read_replay_artifact(
                    self.context,
                    artifact_ref=artifact_ref,
                    artifact_kind=kind,
                )
                if kind == "observation_delta":
                    owner.admit_observation_delta(_observation_delta_from_row(value))
                    reconstructed["observation_delta"] += 1
                elif kind == "observation_delta_batch":
                    for row in value.get("deltas") or ():
                        owner.admit_observation_delta(_observation_delta_from_row(row))
                        reconstructed["observation_delta"] += 1
                elif kind == "proposal_batch":
                    proposals = tuple(
                        _factor_proposal_from_row(row)
                        for row in value.get("proposals") or ()
                    )
                    owner.admit_proposals(proposals, stage=str(value["stage"]))
                elif kind == "solver_receipt":
                    receipt = _solver_receipt_from_row(value)
                    job = owner._pending_jobs.pop(receipt.job_ref, None)
                    if job is None:
                        raise ValueError(
                            "checkpointed solver receipt has no reconstructed job"
                        )
                    owner._in_flight_jobs[receipt.job_ref] = job
                    owner.admit_solver_receipt(receipt)
                else:
                    dirty_before = tuple(
                        sorted(key.owner_ref for key in owner._dirty_groups)
                    )
                    result = owner.reduce_dirty_groups()
                    if (
                        result.resulting_revision != int(value["resulting_revision"])
                        or dirty_before
                        != tuple(sorted(value.get("dirty_owner_refs") or ()))
                        or tuple(result.changed_factor_refs)
                        != tuple(value.get("changed_factor_refs") or ())
                    ):
                        raise ValueError("checkpointed reduction replay diverged")
                if kind not in {"observation_delta", "observation_delta_batch"}:
                    reconstructed[kind] += 1
        finally:
            self.context.reconstructing_owner = False
        unresolved = sorted({*owner._pending_jobs, *owner._in_flight_jobs})
        if owner.revision != int(
            checkpoint.get("current_owner_revision") or 0
        ) or unresolved != sorted(checkpoint.get("unresolved_frontier_refs") or ()):
            raise ValueError("closure owner reconstruction disagrees with checkpoint")
        activation = self.context.closure_activation
        activation["owner_reconstructed"] = True
        activation["reconstructed_admission_count"] = reconstructed["observation_delta"]
        activation["reconstructed_proposal_batch_count"] = reconstructed[
            "proposal_batch"
        ]
        activation["reconstructed_receipt_count"] = reconstructed["solver_receipt"]
        activation["reconstructed_reduction_count"] = reconstructed["dirty_reduction"]
        activation["owner_reconstruction_elapsed_ns"] = monotonic_ns() - started
        self.context.sample(
            "owner_frontier_reconstruction",
            phase="closure_resume",
            counts=dict(reconstructed),
            details={"owner_revision": owner.revision},
            elapsed_ns=activation["owner_reconstruction_elapsed_ns"],
        )

    def record_observation_batch(self, deltas: Iterable[Any], *, owner: Any) -> None:
        started = monotonic_ns()
        new_deltas = tuple(
            delta
            for delta in deltas
            if delta.delta_ref
            not in set(self.context.closure_activation.get("recorded_delta_refs") or ())
        )
        if not new_deltas:
            self.checkpoint_owner(owner, force=True)
            return
        artifact_ref = _write_replay_artifact(
            self.context,
            artifact_kind="observation_delta_batch",
            value={"deltas": [delta.to_dict() for delta in new_deltas]},
        )
        _append_replay_event(
            self.context,
            artifact_kind="observation_delta_batch",
            artifact_ref=artifact_ref,
        )
        recorded = set(self.context.closure_activation.get("recorded_delta_refs") or ())
        recorded.update(delta.delta_ref for delta in new_deltas)
        self.context.closure_activation["recorded_delta_refs"] = tuple(sorted(recorded))
        self.checkpoint_owner(owner, force=True)
        self.context.sample(
            "owner_admission_batch",
            phase="closure_handoff",
            counts={
                "rows_in": len(new_deltas),
                "pending_jobs": len(owner._pending_jobs),
                "owner_revision": owner.revision,
            },
            details={"checkpoint_managed": True},
            elapsed_ns=monotonic_ns() - started,
        )

    def checkpoint_owner(self, owner: Any, *, force: bool = False) -> None:
        self.context.closure_activation["current_owner_revision"] = owner.revision
        self.context.closure_activation["unresolved_frontier_refs"] = tuple(
            sorted({*owner._pending_jobs, *owner._in_flight_jobs})
        )
        self._checkpoint_calls += 1
        interval = _integer_env("SENSIBLAW_CLOSURE_HANDOFF_CHECKPOINT_INTERVAL", 32)
        if force or self._checkpoint_calls % interval == 0:
            _write_closure_handoff_checkpoint(self.context)


def _load_closure_activation_leaf(
    path: Path | None,
    *,
    leaf_ref: str,
    input_identity: list[list[Any]],
    input_digest: str,
) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = _read_json(path)
    if (
        payload is None
        or payload.get("schema_version") != CLOSURE_ACTIVATION_LEAF_SCHEMA_VERSION
        or payload.get("contract_ref") != CLOSURE_ACTIVATION_CONTRACT
        or payload.get("leaf_ref") != leaf_ref
        or payload.get("input_identity") != input_identity
        or payload.get("input_digest") != input_digest
    ):
        raise ValueError(f"closure activation leaf is corrupt: {path.name}")
    if canonical_sha256(payload.get("value")) != payload.get("output_digest"):
        raise ValueError(f"closure activation leaf digest mismatch: {path.name}")
    return payload


def prepare_closure_activation_leaves(
    *,
    context: SemanticExecutionContext,
    observation_deltas: Sequence[Any],
) -> tuple[Any, ...]:
    """Materialize the compatibility view of the ordered activation producer.

    New execution paths consume :func:`iter_closure_activation_leaves` directly.
    Keeping this helper preserves the older test and caller surface without making
    the bounded compiler wait for every physical leaf.
    """

    return tuple(
        delta
        for leaf in iter_closure_activation_leaves(
            context=context, observation_deltas=observation_deltas
        )
        for delta in leaf
    )


def iter_closure_activation_leaves(
    *,
    context: SemanticExecutionContext,
    observation_deltas: Iterable[Any],
) -> Iterator[tuple[Any, ...]]:
    """Yield checkpointed immutable activation leaves in canonical order.

    Workers may finish in any order.  The small ordinal buffer is deliberately
    an execution concern: it contains leaf references/results, never owner state
    or serialised observation deltas.  A consumer draining this iterator applies
    natural backpressure before another future can be submitted.
    """

    from src.policy.parallel_typing_tail import (
        _pool,
        prepare_closure_activation_leaf_worker,
    )

    ordered = tuple(
        sorted(
            observation_deltas, key=lambda row: (int(row.sequence_no), row.delta_ref)
        )
    )
    chunks = tuple(
        ordered[offset : offset + context.closure_activation_leaf_size]
        for offset in range(0, len(ordered), context.closure_activation_leaf_size)
    )
    started = monotonic_ns()
    leaves: dict[int, dict[str, Any]] = {}
    leaf_completed_ns: dict[int, int] = {}
    pending: dict[Any, tuple[int, str, list[list[Any]], str, Path | None]] = {}
    next_submit = 0
    next_ordinal = 0
    reused = 0
    computed = 0
    worker_pids: set[int] = set()
    computed_worker_pids: set[int] = set()
    reused_worker_pids: set[int] = set()
    completed_leaf_refs: list[str] = []
    admitted_leaf_refs: list[str] = []
    max_buffered = 0
    max_buffered_bytes = 0
    activation_input_bytes = 0
    activation_output_bytes = 0
    head_of_line_wait_ns = 0
    executor = _pool()
    worker_count = max(1, _integer_env("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", 1))
    buffer_limit = max(1, 2 * worker_count)
    context.closure_activation.update(
        {
            "contract_ref": CLOSURE_ACTIVATION_CONTRACT,
            "configured_leaf_size": context.closure_activation_leaf_size,
            "leaf_count": len(chunks),
            "admission_order": "sequence_no_delta_ref_ascending",
            "admitted_delta_count": int(
                context.closure_activation.get("reconstructed_admission_count") or 0
            ),
            "new_admission_count": 0,
            "duplicate_admission_count": 0,
            "admitted_batch_refs": (),
            "first_owner_admission_latency_ns": None,
            "first_ready_job_latency_ns": None,
            "owner_admission_started_immediately": False,
            "ready_job_count": 0,
            "admission_elapsed_ns": 0,
            "buffer_limit_leaves": buffer_limit,
        }
    )

    def descriptor(
        ordinal: int,
    ) -> tuple[int, str, list[list[Any]], str, Path | None, tuple[Any, ...]]:
        chunk = chunks[ordinal]
        # ``delta_ref`` is the immutable semantic identity.  The owner never
        # serialises or hashes full deltas merely to schedule physical leaves.
        input_identity = [[int(delta.sequence_no), delta.delta_ref] for delta in chunk]
        input_digest = canonical_sha256(input_identity)
        leaf_ref = "closure-activation:" + canonical_sha256(
            {"ordinal": ordinal, "input_digest": input_digest}
        )
        path = _closure_activation_leaf_path(
            context.closure_activation_checkpoint_root, leaf_ref
        )
        return ordinal, leaf_ref, input_identity, input_digest, path, chunk

    def checkpoint_leaf(
        ordinal: int,
        leaf_ref: str,
        input_identity: list[list[Any]],
        input_digest: str,
        path: Path | None,
        result: Mapping[str, Any],
    ) -> None:
        nonlocal computed, max_buffered, max_buffered_bytes
        nonlocal activation_input_bytes, activation_output_bytes
        value = result["value"]
        pid = int(result["pid"])
        leaf = {
            "schema_version": CLOSURE_ACTIVATION_LEAF_SCHEMA_VERSION,
            "contract_ref": CLOSURE_ACTIVATION_CONTRACT,
            "leaf_ref": leaf_ref,
            "input_identity": input_identity,
            "input_digest": input_digest,
            "value": value,
            "output_digest": canonical_sha256(value),
            "worker_pid": pid,
        }
        if path is not None:
            _atomic_write_json(path, leaf)
        leaves[ordinal] = leaf
        leaf_completed_ns[ordinal] = monotonic_ns()
        completed_leaf_refs.append(leaf_ref)
        computed += 1
        worker_pids.add(pid)
        computed_worker_pids.add(pid)
        max_buffered = max(max_buffered, len(leaves))
        input_bytes = len(json.dumps(input_identity, separators=(",", ":")))
        output_bytes = len(json.dumps(value, separators=(",", ":")))
        activation_input_bytes += input_bytes
        activation_output_bytes += output_bytes
        max_buffered_bytes = max(
            max_buffered_bytes,
            sum(
                len(json.dumps(row.get("value"), separators=(",", ":")))
                for row in leaves.values()
            ),
        )

    while next_ordinal < len(chunks):
        # Submit only the worker window.  A completed out-of-order leaf counts
        # against the same bound until its canonical predecessors are admitted.
        while next_submit < len(chunks) and len(pending) + len(leaves) < buffer_limit:
            ordinal, leaf_ref, input_identity, input_digest, path, chunk = descriptor(
                next_submit
            )
            cached = _load_closure_activation_leaf(
                path,
                leaf_ref=leaf_ref,
                input_identity=input_identity,
                input_digest=input_digest,
            )
            if cached is not None:
                leaves[ordinal] = cached
                leaf_completed_ns[ordinal] = monotonic_ns()
                completed_leaf_refs.append(leaf_ref)
                cached_pid = int(cached.get("worker_pid") or 0)
                if cached_pid:
                    worker_pids.add(cached_pid)
                    reused_worker_pids.add(cached_pid)
                cached_input_bytes = len(
                    json.dumps(input_identity, separators=(",", ":"))
                )
                cached_output_bytes = len(
                    json.dumps(cached.get("value"), separators=(",", ":"))
                )
                activation_input_bytes += cached_input_bytes
                activation_output_bytes += cached_output_bytes
                max_buffered_bytes = max(
                    max_buffered_bytes,
                    sum(
                        len(json.dumps(row.get("value"), separators=(",", ":")))
                        for row in leaves.values()
                    ),
                )
                reused += 1
            elif executor is None:
                checkpoint_leaf(
                    ordinal,
                    leaf_ref,
                    input_identity,
                    input_digest,
                    path,
                    prepare_closure_activation_leaf_worker({"deltas": chunk}),
                )
            else:
                pending[
                    executor.submit(
                        prepare_closure_activation_leaf_worker, {"deltas": chunk}
                    )
                ] = (ordinal, leaf_ref, input_identity, input_digest, path)
            next_submit += 1

        if next_ordinal not in leaves and pending:
            done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in done:
                ordinal, leaf_ref, input_identity, input_digest, path = pending.pop(
                    future
                )
                checkpoint_leaf(
                    ordinal,
                    leaf_ref,
                    input_identity,
                    input_digest,
                    path,
                    future.result(),
                )
        stop_after = _integer_env(
            "SENSIBLAW_CLOSURE_ACTIVATION_STOP_AFTER_LEAVES", 0, minimum=0
        )
        if stop_after and computed >= stop_after:
            raise RuntimeError(
                f"stopped after {computed} checkpointed closure activation leaves"
            )
        if next_ordinal not in leaves:
            continue
        leaf = leaves.pop(next_ordinal)
        completed_ns = leaf_completed_ns.pop(next_ordinal, monotonic_ns())
        head_of_line_wait_ns = max(head_of_line_wait_ns, monotonic_ns() - completed_ns)
        admitted_leaf_refs.append(str(leaf["leaf_ref"]))
        context.closure_activation_completed_ns = monotonic_ns()
        context.closure_activation.update(
            {
                "next_leaf_ordinal": next_ordinal + 1,
                "completed_leaf_refs": tuple(completed_leaf_refs),
                "buffered_leaf_refs": tuple(
                    str(row["leaf_ref"]) for _, row in sorted(leaves.items())
                ),
                "admitted_leaf_refs": tuple(admitted_leaf_refs),
                "max_buffered_leaves": max_buffered,
            }
        )
        _write_closure_handoff_checkpoint(context)
        stop_after_completion = _integer_env(
            "SENSIBLAW_CLOSURE_STOP_AFTER_ACTIVATION_COMPLETION", 0, minimum=0
        )
        if stop_after_completion and len(admitted_leaf_refs) >= stop_after_completion:
            raise RuntimeError("stopped after closure activation completion checkpoint")
        yield chunks[next_ordinal]
        next_ordinal += 1
    elapsed_ns = monotonic_ns() - started
    context.closure_activation.update(
        {
            "computed_leaf_count": computed,
            "reused_leaf_count": reused,
            "worker_pids": sorted(worker_pids),
            "computed_worker_pids": sorted(computed_worker_pids),
            "reused_worker_pids": sorted(reused_worker_pids),
            "activation_elapsed_ns": elapsed_ns,
            "max_buffered_leaves": max_buffered,
            "buffer_limit_leaves": buffer_limit,
            "max_buffered_bytes": max_buffered_bytes,
            "head_of_line_wait_ns": head_of_line_wait_ns,
            "activation_input_bytes": activation_input_bytes,
            "activation_output_bytes": activation_output_bytes,
            "completed_leaf_refs": tuple(completed_leaf_refs),
            "admitted_leaf_refs": tuple(admitted_leaf_refs),
            "buffered_leaf_refs": (),
            "next_leaf_ordinal": next_ordinal,
        }
    )
    _write_closure_handoff_checkpoint(context)
    with context.lock:
        context.closure_counters["activation_leaf_count"] = len(chunks)
        context.closure_counters["activation_leaves_computed"] = computed
        context.closure_counters["activation_leaves_reused"] = reused
        for pid in worker_pids:
            context.closure_counters[f"activation_worker_pid:{pid}"] += 1
    context.sample(
        "activation_result_collection",
        phase="closure_activation_completed",
        counts={
            "leaf_count": len(chunks),
            "computed_leaf_count": computed,
            "reused_leaf_count": reused,
            "input_bytes": activation_input_bytes,
            "output_bytes": activation_output_bytes,
            "max_buffered_bytes": max_buffered_bytes,
        },
        details=dict(context.closure_activation),
        elapsed_ns=elapsed_ns,
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
    original_admit_proposals = BoundedStreamingSemanticOwner.admit_proposals
    original_admit_observation = BoundedStreamingSemanticOwner.admit_observation_delta
    original_admit_receipt = BoundedStreamingSemanticOwner.admit_solver_receipt
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
                "structural_hypotheses": len(kwargs.get("structural_hypotheses") or ()),
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
            context.amplification.update(meet_refinement_report(result[1], result[2]))
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

    def binding_wrapper(artifacts: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
        result = original_binding(artifacts, **kwargs)
        context = _CONTEXT.get()
        if context is not None:
            context.amplification.update(candidate_set_report(result))
        return result

    def reduce_dirty_wrapper(self: Any) -> Any:
        context = _CONTEXT.get() or _context_for_document(self.document_ref)
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
                context.closure_activation["completed_reduction_key_refs"] = tuple(
                    sorted(key.owner_ref for key in dirty)
                )
                context.closure_activation["current_owner_revision"] = self.revision
                context.closure_activation["unresolved_frontier_refs"] = tuple(
                    sorted({*self._pending_jobs, *self._in_flight_jobs})
                )
                if dirty and not context.reconstructing_owner:
                    artifact_ref = _write_replay_artifact(
                        context,
                        artifact_kind="dirty_reduction",
                        value={
                            "prior_revision": result.prior_revision,
                            "resulting_revision": result.resulting_revision,
                            "dirty_owner_refs": [key.owner_ref for key in dirty],
                            "changed_factor_refs": list(result.changed_factor_refs),
                        },
                    )
                    _append_replay_event(
                        context,
                        artifact_kind="dirty_reduction",
                        artifact_ref=artifact_ref,
                    )
            managed_checkpoint = bool(
                context.closure_activation.get("batch_checkpoint_managed")
            )
            if not context.reconstructing_owner and not context.closure_activation.get(
                "batch_checkpoint_managed"
            ):
                context.sample(
                    "dirty_group_reduction",
                    phase="closure_batch",
                    counts={
                        "dirty_groups": len(dirty),
                        "proposals_examined": proposals_examined,
                        "settled_groups_rescanned": settled_rescans,
                        "changed_factors": len(result.changed_factor_refs),
                    },
                    elapsed_ns=monotonic_ns() - started,
                )
            stop_after = _integer_env(
                "SENSIBLAW_CLOSURE_STOP_AFTER_DIRTY_REDUCTIONS", 0, minimum=0
            )
            if not managed_checkpoint or (
                stop_after
                and not context.reconstructing_owner
                and context.closure_counters["reduction_batches"] >= stop_after
            ):
                _write_closure_handoff_checkpoint(context)
            if (
                stop_after
                and not context.reconstructing_owner
                and context.closure_counters["reduction_batches"] >= stop_after
            ):
                raise RuntimeError(
                    f"stopped after {stop_after} checkpointed dirty reductions"
                )
        return result

    def admit_proposals_wrapper(
        self: Any, proposals: Iterable[Any], *, stage: str
    ) -> Any:
        context = _CONTEXT.get() or _context_for_document(self.document_ref)
        batch = tuple(proposals)
        started = monotonic_ns()
        result = original_admit_proposals(self, batch, stage=stage)
        if context is not None and result.accepted_proposal_refs:
            if not context.reconstructing_owner:
                context.sample(
                    "owner_proposal_admission",
                    phase="started",
                    counts={
                        "proposal_count": len(batch),
                        "accepted_proposal_count": len(
                            result.accepted_proposal_refs
                        ),
                    },
                    details={
                        "stage": stage,
                        "current_work_key": f"proposal-batch:{stage}",
                    },
                )
            artifact_ref: str | None = None
            artifact_started = monotonic_ns()
            if not context.reconstructing_owner:
                # Content addressing can walk a large proposal batch.  Keep
                # that physical work outside the shared telemetry/state lock;
                # otherwise every worker appears blocked while the owner
                # hashes an immutable replay artifact.
                artifact_ref = _write_replay_artifact(
                    context,
                    artifact_kind="proposal_batch",
                    value={
                        "stage": stage,
                        "proposals": [row.to_dict() for row in batch],
                    },
                )
                context.sample(
                    "owner_proposal_replay_artifact",
                    phase="completed",
                    counts={
                        "proposal_count": len(batch),
                        "accepted_proposal_count": len(
                            result.accepted_proposal_refs
                        ),
                    },
                    details={
                        "stage": stage,
                        "artifact_ref": artifact_ref,
                    },
                    elapsed_ns=monotonic_ns() - artifact_started,
                )
            with context.lock:
                counter_key = (
                    "reconstructed_proposals_admitted"
                    if context.reconstructing_owner
                    else "new_proposals_admitted"
                )
                context.closure_counters[counter_key] += len(
                    result.accepted_proposal_refs
                )
                if artifact_ref is not None:
                    _append_replay_event(
                        context,
                        artifact_kind="proposal_batch",
                        artifact_ref=artifact_ref,
                    )
                context.closure_activation["current_owner_revision"] = self.revision
                context.closure_activation["unresolved_frontier_refs"] = tuple(
                    sorted({*self._pending_jobs, *self._in_flight_jobs})
                )
            if not context.closure_activation.get("batch_checkpoint_managed"):
                _write_closure_handoff_checkpoint(context)
            if not context.reconstructing_owner:
                context.sample(
                    "owner_proposal_admission",
                    phase="closure_handoff",
                    counts={
                        "proposal_count": len(batch),
                        "accepted_proposal_count": len(result.accepted_proposal_refs),
                    },
                    details={"stage": stage, "owner_revision": self.revision},
                    elapsed_ns=monotonic_ns() - started,
                )
        return result

    def admit_receipt_wrapper(self: Any, receipt: Any) -> Any:
        context = _context_for_document(receipt.owner_key.document_ref)
        result = original_admit_receipt(self, receipt)
        if context is not None:
            if not context.reconstructing_owner:
                receipt_path = context.closure_receipt_path(receipt.job_ref)
                if receipt_path is not None and not receipt_path.exists():
                    _atomic_write_json(receipt_path, receipt.to_dict())
                artifact_ref = (
                    "closure-receipt-artifact:"
                    + receipt.job_ref.split(":", maxsplit=1)[1]
                )
                _append_replay_event(
                    context,
                    artifact_kind="solver_receipt",
                    artifact_ref=artifact_ref,
                )
                context.closure_counters["new_receipts_admitted"] += 1
            else:
                context.closure_counters["reconstructed_receipts_admitted"] += 1
            context.closure_activation["current_owner_revision"] = self.revision
            context.closure_activation["unresolved_frontier_refs"] = tuple(
                sorted({*self._pending_jobs, *self._in_flight_jobs})
            )
            if not context.closure_activation.get("batch_checkpoint_managed"):
                _write_closure_handoff_checkpoint(context)
        return result

    def admit_observation_wrapper(self: Any, delta: Any) -> Any:
        context = _context_for_document(delta.document_ref)
        started = monotonic_ns()
        pending_before = len(self._pending_jobs)
        already_admitted = delta.delta_ref in self._observation_deltas
        result = original_admit_observation(self, delta)
        if context is not None and context.closure_activation:
            finished = monotonic_ns()
            with context.lock:
                context.closure_activation["admission_elapsed_ns"] = int(
                    context.closure_activation.get("admission_elapsed_ns") or 0
                ) + (finished - started)
                if context.reconstructing_owner:
                    admission_kind = "reconstructed"
                elif already_admitted:
                    admission_kind = "duplicate"
                else:
                    admission_kind = "new"
                context.closure_counters[f"activation_deltas_{admission_kind}"] += 1
                context.closure_activation[f"{admission_kind}_admission_count"] = (
                    int(
                        context.closure_activation.get(
                            f"{admission_kind}_admission_count"
                        )
                        or 0
                    )
                    + 1
                )
                if admission_kind != "duplicate":
                    context.closure_activation["admitted_delta_count"] = (
                        int(context.closure_activation.get("admitted_delta_count") or 0)
                        + 1
                    )
                batch_ref = str(getattr(delta, "batch_ref", ""))
                admitted_batches = set(
                    context.closure_activation.get("admitted_batch_refs") or ()
                )
                if batch_ref:
                    admitted_batches.add(batch_ref)
                context.closure_activation["admitted_batch_refs"] = tuple(
                    sorted(admitted_batches)
                )
                context.closure_activation["current_owner_revision"] = self.revision
                context.closure_activation["unresolved_frontier_refs"] = tuple(
                    sorted({*self._pending_jobs, *self._in_flight_jobs})
                )
                if admission_kind == "new" and not context.closure_activation.get(
                    "batch_checkpoint_managed"
                ):
                    artifact_ref = _write_replay_artifact(
                        context,
                        artifact_kind="observation_delta",
                        value=delta.to_dict(),
                    )
                    _append_replay_event(
                        context,
                        artifact_kind="observation_delta",
                        artifact_ref=artifact_ref,
                    )
                completed_ns = context.closure_activation_completed_ns
                if (
                    context.closure_activation.get("first_owner_admission_latency_ns")
                    is None
                    and completed_ns is not None
                ):
                    context.closure_activation["first_owner_admission_latency_ns"] = (
                        max(0, started - completed_ns)
                    )
                    # Admission is entered directly from the prepared ordered
                    # delta sequence; no leaf value is re-expanded on this path.
                    context.closure_activation[
                        "owner_admission_started_immediately"
                    ] = True
                    context.closure_activation["activation_owner_overlap_observed"] = (
                        int(context.closure_activation.get("next_leaf_ordinal") or 0)
                        < int(context.closure_activation.get("leaf_count") or 0)
                    )
                ready_created = max(0, len(self._pending_jobs) - pending_before)
                context.closure_activation["ready_job_count"] = (
                    int(context.closure_activation.get("ready_job_count") or 0)
                    + ready_created
                )
                context.closure_activation["total_ready_job_count"] = int(
                    context.closure_activation["ready_job_count"]
                )
                if (
                    ready_created
                    and context.closure_activation.get("first_ready_job_latency_ns")
                    is None
                    and completed_ns is not None
                ):
                    context.closure_activation["first_ready_job_latency_ns"] = max(
                        0, finished - completed_ns
                    )
            if not context.reconstructing_owner and not context.closure_activation.get(
                "batch_checkpoint_managed"
            ):
                context.sample(
                    "owner_admission_batch",
                    phase="closure_handoff",
                    counts={
                        "rows_in": 1,
                        "rows_out": ready_created,
                        "pending_jobs": len(self._pending_jobs),
                    },
                    details={"owner_revision": self.revision},
                    elapsed_ns=finished - started,
                )
            managed_checkpoint = bool(
                context.closure_activation.get("batch_checkpoint_managed")
            )
            stop_after = _integer_env(
                "SENSIBLAW_CLOSURE_STOP_AFTER_OWNER_BATCH_ADMISSIONS", 0, minimum=0
            )
            if not managed_checkpoint:
                _write_closure_handoff_checkpoint(context)
            if (
                stop_after
                and not context.reconstructing_owner
                and not managed_checkpoint
                and int(context.closure_activation.get("new_admission_count") or 0)
                >= stop_after
            ):
                raise RuntimeError(
                    f"stopped after {stop_after} checkpointed owner admissions"
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
                len(proposal.dependency_factor_refs) for proposal in receipt.proposals
            )
        stop_after = _integer_env("SENSIBLAW_CLOSURE_STOP_AFTER_RECEIPTS", 0, minimum=0)
        if stop_after and context.closure_counters["receipts_computed"] >= stop_after:
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
        if context is not None:
            deltas = kwargs.get("observation_deltas")
            if deltas is None:
                raise ValueError("streaming closure requires named observation_deltas")
            kwargs["observation_deltas"] = iter_closure_activation_leaves(
                context=context,
                observation_deltas=deltas,
            )
            replay_contract = ClosureOwnerReplayContract(context)
            context.closure_activation["batch_checkpoint_managed"] = True
            kwargs["replay_contract"] = replay_contract
        started = monotonic_ns()
        result = original_streaming(*args, **kwargs)
        if context is not None:
            _build, metrics = result
            kernel_telemetry = dict(metrics.get("kernel_telemetry") or {})
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
                context.closure_activation["kernel_telemetry"] = kernel_telemetry
                context.closure_activation["fixed_point_certificate"] = dict(
                    _build.get("fixed_point_certificate") or {}
                )
            for stage_name, telemetry in kernel_telemetry.items():
                if not isinstance(telemetry, Mapping):
                    continue
                counts = telemetry.get("counts") or {
                    key: int(value)
                    for key, value in telemetry.items()
                    if isinstance(value, int) and not key.endswith("_ns")
                }
                elapsed = telemetry.get("elapsed_ns")
                elapsed_total = (
                    sum(int(value) for value in elapsed.values())
                    if isinstance(elapsed, Mapping)
                    else sum(
                        int(value)
                        for key, value in telemetry.items()
                        if isinstance(value, int) and key.endswith("_ns")
                    )
                )
                context.sample(
                    f"closure_{stage_name}",
                    phase="kernel_completed",
                    counts=counts,
                    details=telemetry,
                    elapsed_ns=elapsed_total,
                )
            context.sample(
                "streaming_closure:fixed_point",
                phase="kernel_completed",
                counts={
                    "jobs_completed": context.closure_counters["jobs_completed"],
                    "proposals_examined": context.closure_counters[
                        "proposals_examined"
                    ],
                    "proposals_emitted": context.closure_counters["proposals_emitted"],
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
    BoundedStreamingSemanticOwner.admit_proposals = admit_proposals_wrapper
    BoundedStreamingSemanticOwner.admit_observation_delta = admit_observation_wrapper
    BoundedStreamingSemanticOwner.admit_solver_receipt = admit_receipt_wrapper
    PythonClosureExecutor.execute = execute_wrapper
    operational._streaming_semantic_build = streaming_wrapper
    operational.compile_document_operational = compile_wrapper
    operational._canonical_compile_document_operational = original_compile
    operational._bounded_streaming_semantic_build = original_streaming
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = [
    "CLOSURE_ACTIVATION_CONTRACT",
    "CLOSURE_ACTIVATION_LEAF_SCHEMA_VERSION",
    "CLOSURE_HANDOFF_CONTRACT",
    "CLOSURE_HANDOFF_SCHEMA_VERSION",
    "CLOSURE_REPLAY_CONTRACT",
    "ClosureOwnerReplayContract",
    "SEMANTIC_EXECUTION_SCHEMA_VERSION",
    "SemanticExecutionContext",
    "indexed_atom_mention_refs",
    "indexed_parser_observation_refs_by_mention",
    "install_parallel_semantic_execution",
    "iter_closure_activation_leaves",
    "prepare_closure_activation_leaves",
]
