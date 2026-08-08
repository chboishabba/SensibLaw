"""Ordered document-world publication with bounded parser-only lookahead.

The semantic compiler is an ordered fold::

    W_0 --compile D_1--> W_1 --compile D_2--> ... --compile D_n--> W_n

Only parser observations may run ahead of that frontier.  They are immutable,
document-local evidence and are persisted only in the existing parser-fibre
checkpoint directory.  Mention licensing, PNF closure, demand discharge,
canonical identity, PostgreSQL publication, and world extension remain strictly
ordered one document at a time.

This module is deliberately an execution wrapper around
``compile_directory_postgres``.  It does not introduce a second compiler and it
does not give parser fibres semantic authority.
"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
import json
from multiprocessing import get_context
import os
from pathlib import Path
import tempfile
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.pnf.document_fibres import DocumentFibrePolicy


ORDERED_WORLD_LOOKAHEAD_CONTRACT = "ordered-world-parser-lookahead:v0_1"
ORDERED_WORLD_LOOKAHEAD_STATE_SCHEMA = "sl.ordered_world_parser_lookahead.v0_1"


@dataclass(frozen=True)
class ParserLookaheadAllocation:
    """A global-budget-preserving split between the two physical lanes."""

    global_worker_budget: int
    foreground_worker_budget: int
    parser_lookahead_workers: int
    enabled: bool
    reason: str

    def __post_init__(self) -> None:
        if self.global_worker_budget < 1:
            raise ValueError("global_worker_budget must be positive")
        if self.foreground_worker_budget < 1:
            raise ValueError("foreground_worker_budget must be positive")
        if self.parser_lookahead_workers < 0:
            raise ValueError("parser_lookahead_workers must be non-negative")
        if (
            self.foreground_worker_budget + self.parser_lookahead_workers
            > self.global_worker_budget
        ):
            raise ValueError("ordered-world lanes exceed the global worker budget")

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_worker_budget": self.global_worker_budget,
            "foreground_worker_budget": self.foreground_worker_budget,
            "parser_lookahead_workers": self.parser_lookahead_workers,
            "enabled": self.enabled,
            "reason": self.reason,
        }


def allocate_parser_lookahead(
    *, global_worker_budget: int, parser_workers: int
) -> ParserLookaheadAllocation:
    """Reserve a parser lane without changing parser-fibre identity.

    ``DocumentFibrePolicy`` currently includes worker count in its checkpoint
    identity.  The lookahead lane must therefore use exactly the same
    ``parser_workers`` value as foreground replay.  We enable overlap only when
    the global budget can reserve that many workers for both lanes.  Otherwise
    compilation remains ordered and simply parses inline.
    """

    if global_worker_budget < 1:
        raise ValueError("worker_budget must be positive")
    if not 1 <= parser_workers <= 32:
        raise ValueError("parser_workers must be between 1 and 32")
    required = 2 * parser_workers
    if global_worker_budget < required:
        return ParserLookaheadAllocation(
            global_worker_budget=global_worker_budget,
            foreground_worker_budget=global_worker_budget,
            parser_lookahead_workers=0,
            enabled=False,
            reason=(
                "insufficient_budget_to_preserve_parser_checkpoint_identity:"
                f"required={required}"
            ),
        )
    return ParserLookaheadAllocation(
        global_worker_budget=global_worker_budget,
        foreground_worker_budget=global_worker_budget - parser_workers,
        parser_lookahead_workers=parser_workers,
        enabled=True,
        reason="bounded_parser_lane_reserved",
    )


@dataclass(frozen=True)
class ParserPrefetchCandidate:
    """World-independent input required to materialise parser checkpoints."""

    sequence_no: int
    document_ref: str
    relative_path: str
    source_path: str
    media_type: str
    source_ref: str
    checkpoint_dir: str
    canonical_chars: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_no": self.sequence_no,
            "document_ref": self.document_ref,
            "relative_path": self.relative_path,
            "source_path": self.source_path,
            "media_type": self.media_type,
            "source_ref": self.source_ref,
            "checkpoint_dir": self.checkpoint_dir,
            "canonical_chars": self.canonical_chars,
        }


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _completed_document_refs(state_path: Path | None) -> set[str]:
    if state_path is None or not state_path.exists():
        return set()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return set()
    documents = payload.get("documents") if isinstance(payload, Mapping) else None
    if not isinstance(documents, Mapping):
        return set()
    return {
        str(document_ref)
        for document_ref, row in documents.items()
        if isinstance(row, Mapping)
        and str(row.get("state") or "") in {"compiled", "reused_compilation"}
    }


def _prefetch_document_worker(
    candidate: Mapping[str, Any], policy_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Spawn-safe parser-only worker; no world or PostgreSQL mutation occurs."""

    from src.pnf.document_fibres import DocumentFibrePolicy, parse_document_fibres
    from src.policy.postgres_corpus_compilation import _canonical_source_coordinates
    from src.sensiblaw.interfaces import parse_canonical_text

    started_ns = monotonic_ns()
    source_path = Path(str(candidate["source_path"]))
    source_text = source_path.read_bytes().decode("utf-8")
    canonical_text, _canonical_sha256, _adapter_ref = _canonical_source_coordinates(
        media_type=str(candidate["media_type"]),
        source_text=source_text,
        source_ref=str(candidate["source_ref"]),
    )
    if len(canonical_text) != int(candidate["canonical_chars"]):
        raise ValueError("parser lookahead canonical length changed after inventory")
    policy = DocumentFibrePolicy(
        workers=int(policy_payload["workers"]),
        parser_limit_chars=int(policy_payload["parser_limit_chars"]),
        target_chars=int(policy_payload["target_chars"]),
        overlap_chars=int(policy_payload["overlap_chars"]),
        adaptive_partitioning=bool(policy_payload["adaptive_partitioning"]),
    )
    if not policy.should_partition(canonical_text):
        raise ValueError("parser lookahead candidate no longer requires fibres")
    parsed = parse_document_fibres(
        document_ref=str(candidate["document_ref"]),
        canonical_text=canonical_text,
        parser=parse_canonical_text,
        policy=policy,
        checkpoint_dir=str(candidate["checkpoint_dir"]),
        progress=None,
    )
    receipt = dict(parsed.get("parser_receipt") or {})
    close = getattr(parsed, "close", None)
    if callable(close):
        close()
    return {
        "document_ref": str(candidate["document_ref"]),
        "relative_path": str(candidate["relative_path"]),
        "checkpoint_dir": str(candidate["checkpoint_dir"]),
        "canonical_chars": len(canonical_text),
        "fibre_count": int(receipt.get("fibre_count") or 0),
        "reused_fibre_count": int(receipt.get("reused_fibre_count") or 0),
        "elapsed_ms": max(0, (monotonic_ns() - started_ns) // 1_000_000),
        "authority": "parser_observation_only",
    }


class OrderedWorldParserLookahead:
    """Keep at most one parsed heavy document ahead of the semantic frontier."""

    def __init__(
        self,
        *,
        candidates: Sequence[ParserPrefetchCandidate],
        parser_policy: DocumentFibrePolicy,
        receipt_path: Path,
        allocation: ParserLookaheadAllocation,
    ) -> None:
        self._candidates = tuple(candidates)
        self._policy = parser_policy
        self._receipt_path = receipt_path
        self._allocation = allocation
        self._executor: ProcessPoolExecutor | None = None
        self._active_candidate: ParserPrefetchCandidate | None = None
        self._active_future: Future[dict[str, Any]] | None = None
        self._next_index = 0
        self._results: list[dict[str, Any]] = []
        self._state = "created"

    @property
    def candidate_document_refs(self) -> tuple[str, ...]:
        return tuple(row.document_ref for row in self._candidates)

    def _receipt_payload(self) -> dict[str, Any]:
        return {
            "schema_version": ORDERED_WORLD_LOOKAHEAD_STATE_SCHEMA,
            "contract_ref": ORDERED_WORLD_LOOKAHEAD_CONTRACT,
            "state": self._state,
            "semantic_frontier": "single_ordered_document_publication",
            "parser_lane_authority": "parser_observation_only",
            "buffered_document_limit": 1,
            "allocation": self._allocation.to_dict(),
            "candidate_count": len(self._candidates),
            "candidates": [row.to_dict() for row in self._candidates],
            "active_document_ref": (
                self._active_candidate.document_ref
                if self._active_candidate is not None
                else None
            ),
            "completed_prefetches": list(self._results),
        }

    def _write_receipt(self) -> None:
        _atomic_json_write(self._receipt_path, self._receipt_payload())

    def start(self) -> None:
        if not self._allocation.enabled or not self._candidates:
            self._state = "disabled"
            self._write_receipt()
            return
        self._executor = ProcessPoolExecutor(
            max_workers=1,
            mp_context=get_context("spawn"),
        )
        self._state = "running"
        self._schedule_next()

    def _schedule_next(self) -> None:
        if self._executor is None or self._active_future is not None:
            self._write_receipt()
            return
        if self._next_index >= len(self._candidates):
            self._state = "drained"
            self._write_receipt()
            return
        candidate = self._candidates[self._next_index]
        self._next_index += 1
        self._active_candidate = candidate
        self._active_future = self._executor.submit(
            _prefetch_document_worker,
            candidate.to_dict(),
            self._policy.to_dict(),
        )
        self._write_receipt()

    def wait_for(self, document_ref: str) -> dict[str, Any] | None:
        """Fence semantic use of a document behind its active parser prefetch."""

        if self._active_candidate is None or self._active_future is None:
            return None
        if self._active_candidate.document_ref != document_ref:
            return None
        result = self._active_future.result()
        self._results.append(result)
        self._active_candidate = None
        self._active_future = None
        # As soon as the foreground consumes this checkpoint, the single
        # buffered slot becomes available for the next heavy document.
        self._schedule_next()
        return result

    def close(self) -> None:
        if self._executor is None:
            if self._state == "created":
                self._state = "disabled"
                self._write_receipt()
            return
        try:
            if self._active_future is not None:
                result = self._active_future.result()
                self._results.append(result)
                self._active_future = None
                self._active_candidate = None
        finally:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
            self._state = "completed"
            self._write_receipt()


@contextmanager
def _cooperative_parser_replay(
    coordinator: OrderedWorldParserLookahead,
):
    """Make foreground parsing wait rather than duplicate an active prefetch."""

    import src.policy.operational_corpus_compilation as operational

    original = operational.parse_document_fibres

    def cooperative_parse_document_fibres(*args: Any, **kwargs: Any) -> Any:
        document_ref = str(kwargs.get("document_ref") or "")
        if document_ref:
            coordinator.wait_for(document_ref)
        return original(*args, **kwargs)

    operational.parse_document_fibres = cooperative_parse_document_fibres
    try:
        yield
    finally:
        operational.parse_document_fibres = original


def _lookahead_candidates(
    input_dir: str | Path,
    *,
    context: Any,
    state_path: Path,
    parser_policy: DocumentFibrePolicy,
    recursive: bool,
    follow_symlinks: bool,
    include_globs: Sequence[str],
    exclude_globs: Sequence[str],
    max_files: int | None,
    max_file_bytes: int | None,
    max_total_bytes: int | None,
    admission_policy: Callable[[Mapping[str, Any]], bool] | None,
) -> tuple[ParserPrefetchCandidate, ...]:
    """Select heavy documents by work, not by equal document-count buckets."""

    from src.policy.corpus_compilation import build_corpus_manifest
    from src.policy.postgres_corpus_compilation import (
        _canonical_source_coordinates,
        _prepare_operational_manifest,
    )

    root = Path(input_dir).resolve()
    manifest = build_corpus_manifest(
        root,
        context=context,
        recursive=recursive,
        follow_symlinks=follow_symlinks,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    manifest_row, prepared_sources = _prepare_operational_manifest(
        root=root,
        manifest=manifest.to_dict(),
        context=context,
    )
    completed = _completed_document_refs(state_path)
    candidates: list[ParserPrefetchCandidate] = []
    for sequence_no, entry in enumerate(manifest_row["ordered_documents"], start=1):
        if str(entry.get("status") or "") != "inventoried":
            continue
        if admission_policy is not None and not admission_policy(entry):
            continue
        document_ref = str(entry["document_ref"])
        if document_ref in completed:
            continue
        relative_path = str(entry["relative_path"])
        prepared = prepared_sources.get(relative_path)
        if prepared is None:
            source_text = (root / relative_path).read_bytes().decode("utf-8")
        else:
            _source_bytes, source_text = prepared
        canonical_text, _canonical_sha256, _adapter_ref = (
            _canonical_source_coordinates(
                media_type=str(entry["media_type"]),
                source_text=source_text,
                source_ref=f"document-source:{document_ref}",
            )
        )
        if not parser_policy.should_partition(canonical_text):
            continue
        checkpoint_dir = (
            state_path.parent
            / f"{state_path.stem}_chunks"
            / document_ref.removeprefix("document:")
        )
        candidates.append(
            ParserPrefetchCandidate(
                sequence_no=sequence_no,
                document_ref=document_ref,
                relative_path=relative_path,
                source_path=str(root / relative_path),
                media_type=str(entry["media_type"]),
                source_ref=f"document-source:{document_ref}",
                checkpoint_dir=str(checkpoint_dir),
                canonical_chars=len(canonical_text),
            )
        )
    return tuple(candidates)


def compile_directory_postgres_ordered_world(
    input_dir: str | Path,
    **compile_kwargs: Any,
) -> Any:
    """Compile an ordered world fold while pre-parsing one heavy document.

    This is signature-compatible with ``compile_directory_postgres`` for the
    complete-tranche runner.  ``document_workers`` must remain one because that
    parameter otherwise enables concurrent semantic publication.  The existing
    ``parser_workers`` and ``worker_budget`` parameters control the two physical
    lanes without changing the compiler's semantic contract.
    """

    document_workers = int(compile_kwargs.get("document_workers", 1))
    if document_workers != 1:
        raise ValueError(
            "ordered world compilation requires document_workers=1; "
            "parallelism belongs in parser fibres and document-local closure"
        )

    from src.policy.postgres_corpus_compilation import compile_directory_postgres

    if os.environ.get("SENSIBLAW_ORDERED_WORLD_LOOKAHEAD", "1") == "0":
        return compile_directory_postgres(input_dir, **compile_kwargs)

    state_value = compile_kwargs.get("state_path")
    if state_value is None:
        return compile_directory_postgres(input_dir, **compile_kwargs)
    state_path = Path(state_value).resolve()
    parser_workers = int(compile_kwargs.get("parser_workers", 2))
    worker_budget = int(
        compile_kwargs.get("worker_budget")
        if compile_kwargs.get("worker_budget") is not None
        else max(1, parser_workers)
    )
    allocation = allocate_parser_lookahead(
        global_worker_budget=worker_budget,
        parser_workers=parser_workers,
    )
    parser_policy = DocumentFibrePolicy(
        workers=parser_workers,
        parser_limit_chars=int(compile_kwargs.get("parser_limit_chars", 1_000_000)),
        target_chars=int(compile_kwargs.get("parser_target_chars", 400_000)),
        overlap_chars=int(compile_kwargs.get("parser_overlap_chars", 8_192)),
    )
    candidates: tuple[ParserPrefetchCandidate, ...] = ()
    if allocation.enabled:
        candidates = _lookahead_candidates(
            input_dir,
            context=compile_kwargs["context"],
            state_path=state_path,
            parser_policy=parser_policy,
            recursive=bool(compile_kwargs.get("recursive", True)),
            follow_symlinks=bool(compile_kwargs.get("follow_symlinks", False)),
            include_globs=tuple(compile_kwargs.get("include_globs") or ()),
            exclude_globs=tuple(compile_kwargs.get("exclude_globs") or ()),
            max_files=compile_kwargs.get("max_files"),
            max_file_bytes=compile_kwargs.get("max_file_bytes"),
            max_total_bytes=compile_kwargs.get("max_total_bytes"),
            admission_policy=compile_kwargs.get("admission_policy"),
        )
    receipt_path = state_path.with_name(
        f"{state_path.stem}_parser_lookahead.json"
    )
    coordinator = OrderedWorldParserLookahead(
        candidates=candidates,
        parser_policy=parser_policy,
        receipt_path=receipt_path,
        allocation=allocation,
    )
    resource_ledger = compile_kwargs.get("resource_ledger")
    if resource_ledger is not None:
        resource_ledger.sample(
            "ordered_world_parser_lookahead:start",
            phase="parser_lookahead",
            semantic_counts={"candidate_documents": len(candidates)},
            details={
                "contract_ref": ORDERED_WORLD_LOOKAHEAD_CONTRACT,
                "allocation": allocation.to_dict(),
            },
        )
    coordinator.start()
    foreground_kwargs = dict(compile_kwargs)
    if allocation.enabled and candidates:
        foreground_kwargs["worker_budget"] = allocation.foreground_worker_budget
    try:
        with _cooperative_parser_replay(coordinator):
            result = compile_directory_postgres(input_dir, **foreground_kwargs)
    finally:
        coordinator.close()
    if resource_ledger is not None:
        resource_ledger.sample(
            "ordered_world_parser_lookahead:after",
            phase="parser_lookahead",
            semantic_counts={"candidate_documents": len(candidates)},
            details={
                "contract_ref": ORDERED_WORLD_LOOKAHEAD_CONTRACT,
                "receipt_ref": str(receipt_path),
            },
        )
    return result


__all__ = [
    "ORDERED_WORLD_LOOKAHEAD_CONTRACT",
    "OrderedWorldParserLookahead",
    "ParserLookaheadAllocation",
    "ParserPrefetchCandidate",
    "allocate_parser_lookahead",
    "compile_directory_postgres_ordered_world",
]
