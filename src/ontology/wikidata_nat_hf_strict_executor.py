from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Lock
from typing import Any

from src.ontology.wikidata_nat_hf_partial_read import (
    RateLimiter,
    _default_repl_runner,
    _parse_probe_output,
    _resolve_probe_payload,
    fetch_live_wikidata_statement_payload,
    node_of_name_chunks,
)
from src.ontology.wikidata_nat_hf_selector import (
    _evaluate_manifest,
    _fetch_manifest_cached,
    _preflight_selector,
)
from src.policy.carriers.canonical import canonical_sha256
from src.sources.rate_limit import RateLimit, TokenBucketRateLimiter


STRICT_PARTIAL_READ_SCHEMA_VERSION = "sl.nat_zelph_hf_partial_read.v0_2"
STRICT_EXECUTOR_ID = "sensiblaw.nat_hf_selector.strict.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(values: Any) -> list[str]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def _signal_receipt(exit_code: int) -> dict[str, Any]:
    if exit_code < 0:
        signal_number = -exit_code
        return {
            "termination_kind": "signal",
            "signal_number": signal_number,
            "signal_name": "SIGSEGV" if signal_number == 11 else f"signal_{signal_number}",
        }
    return {
        "termination_kind": "nonzero_exit",
        "signal_number": None,
        "signal_name": None,
    }


def resolve_qids_via_hosted_partial_scan_strict(
    manifest: Mapping[str, Any],
    qids: Sequence[str],
    *,
    zelph_bin: str | None = None,
    language: str = "wikidata",
    max_chunks: int | None = None,
    timeout_seconds: float = 120.0,
    repl_runner: Any | None = None,
    worker_budget: int | None = None,
    rate_limiter: RateLimiter | None = None,
) -> dict[str, Any]:
    """Hosted nodeOfName scan with fail-closed ordered semantics.

    Physical chunk reads may overlap, but semantic outcomes are committed in
    ascending chunk order exactly as the historical serial loop would observe
    them. A later speculative crash therefore cannot defeat an earlier clean
    resolution that would have stopped the serial scan before that later chunk.

    Clean exhaustion is the only route to ``status=partial``. A semantically
    committed runner exception is ``engine_unavailable``; a semantically
    committed non-zero Zelph exit is ``engine_failed``. Every physical launch
    acquires from one shared SensibLaw token bucket before the subprocess starts.

    Injected runners default to one worker for deterministic legacy/unit-fixture
    behaviour; the production path (no injected runner) defaults to four.
    """

    requested = _text_list(qids)
    if not requested:
        raise ValueError("strict partial QID scan requires at least one QID")

    binary = _text(zelph_bin or os.environ.get("ZELPH_BIN") or shutil.which("zelph"))
    workers = max(
        1,
        int(
            worker_budget
            if worker_budget is not None
            else (1 if repl_runner is not None else 4)
        ),
    )
    if not binary:
        return {
            "schema_version": STRICT_PARTIAL_READ_SCHEMA_VERSION,
            "status": "engine_unavailable",
            "failure_kind": "zelph_binary_unavailable",
            "requested_qids": requested,
            "resolved_qids": {},
            "resolved_qid_chunks": {},
            "qid_route_cache_seed": {},
            "unresolved_qids": requested,
            "chunks_scanned": [],
            "chunk_count_scanned": 0,
            "execution_strategy": "bounded_rate_limited_parallel_ordered_commit",
            "worker_budget": workers,
            "network_performed": False,
            "route_index_required": False,
            "full_graph_loaded": False,
            "name_probe": "dot_node_non_creating",
            "nonzero_exit_means_no_match": False,
        }

    chunks = node_of_name_chunks(manifest, language=language)
    if max_chunks is not None:
        chunks = chunks[: max(0, int(max_chunks))]

    limiter = rate_limiter or TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1))
    limiter_cfg = getattr(limiter, "cfg", None)
    runner = repl_runner or _default_repl_runner
    resolved: dict[str, int] = {}
    resolved_chunks: dict[str, int] = {}
    scanned: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None

    stats_lock = Lock()
    active_runner_count = 0
    peak_in_flight = 0
    chunks_launched = 0

    with tempfile.TemporaryDirectory(prefix="sensiblaw-nat-hf-strict-") as tmp:
        manifest_path = Path(tmp) / "wikidata.hf-v2.json"
        import json

        manifest_path.write_text(
            json.dumps(dict(manifest), indent=2, sort_keys=True), encoding="utf-8"
        )

        def run_chunk(
            position: int, chunk: Mapping[str, Any]
        ) -> tuple[int, dict[str, Any], str, tuple[str, ...]]:
            nonlocal active_runner_count, peak_in_flight, chunks_launched
            chunk_index = int(chunk["chunkIndex"])
            # Probe all requested QIDs. Ordered semantic commit below discards
            # already-resolved QIDs exactly as the serial loop would have done.
            probe_qids = tuple(requested)
            try:
                limiter.acquire()
            except Exception as exc:
                return (
                    position,
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "size_bytes": chunk.get("length"),
                        "exit_code": None,
                        "error": f"rate admission failed: {type(exc).__name__}: {exc}",
                        "failure_kind": "rate_admission_failed",
                    },
                    "",
                    probe_qids,
                )

            with stats_lock:
                active_runner_count += 1
                chunks_launched += 1
                peak_in_flight = max(peak_in_flight, active_runner_count)

            payload = _resolve_probe_payload(
                manifest_path=manifest_path,
                chunk_index=chunk_index,
                qids=probe_qids,
                language=language,
            )
            try:
                exit_code, output = runner(
                    binary, payload, timeout_seconds=timeout_seconds
                )
                return (
                    position,
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "size_bytes": chunk.get("length"),
                        "exit_code": int(exit_code),
                    },
                    output,
                    probe_qids,
                )
            except Exception as exc:
                return (
                    position,
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "size_bytes": chunk.get("length"),
                        "exit_code": None,
                        "error": f"{type(exc).__name__}: {exc}",
                        "failure_kind": "runner_exception",
                        "exception_type": type(exc).__name__,
                        "exception_detail": str(exc),
                    },
                    "",
                    probe_qids,
                )
            finally:
                with stats_lock:
                    active_runner_count -= 1

        next_submit_position = 0
        next_commit_position = 0
        semantic_stopped = False
        semantic_stopping_chunk: int | None = None
        chunks_cancelled_before_start = 0
        committed_chunk_count = 0
        completed_buffer: dict[
            int, tuple[dict[str, Any], str, tuple[str, ...]]
        ] = {}
        pending: dict[
            Future[tuple[int, dict[str, Any], str, tuple[str, ...]]], int
        ] = {}

        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="sensiblaw-nat-hf-strict"
        ) as pool:

            def submit_available() -> None:
                nonlocal next_submit_position
                # Bound speculation by submitted-but-not-semantically-committed
                # work, not merely by currently running futures.
                while (
                    not semantic_stopped
                    and len(pending) + len(completed_buffer) < workers
                    and next_submit_position < len(chunks)
                ):
                    position = next_submit_position
                    next_submit_position += 1
                    pending[pool.submit(run_chunk, position, chunks[position])] = position

            submit_available()
            while pending or completed_buffer:
                if pending:
                    completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                    for future in completed:
                        position = pending.pop(future)
                        result_position, row, output, probe_qids = future.result()
                        assert result_position == position
                        scanned.append(dict(row))
                        completed_buffer[position] = (row, output, probe_qids)

                # Physical completion order is erased here. Only the next serial
                # position may affect resolution or failure state.
                while not semantic_stopped and next_commit_position in completed_buffer:
                    row, output, probe_qids = completed_buffer.pop(next_commit_position)
                    committed_chunk_count += 1
                    chunk_index = int(row["chunk_index"])
                    semantic_stopping_chunk = chunk_index

                    failure_kind = _text(row.get("failure_kind"))
                    if failure_kind == "rate_admission_failed":
                        failure = {
                            "failure_kind": "runner_exception",
                            "exception_type": "RateAdmissionError",
                            "exception_detail": _text(row.get("error")),
                            "chunk_index": chunk_index,
                            "object_path": _text(row.get("object_path")),
                        }
                        semantic_stopped = True
                        break
                    if failure_kind == "runner_exception":
                        failure = {
                            "failure_kind": "runner_exception",
                            "exception_type": _text(row.get("exception_type")),
                            "exception_detail": _text(row.get("exception_detail")),
                            "chunk_index": chunk_index,
                            "object_path": _text(row.get("object_path")),
                        }
                        semantic_stopped = True
                        break

                    exit_code = int(row.get("exit_code", 0))
                    if exit_code != 0:
                        failure = {
                            "failure_kind": "zelph_process_failed",
                            "chunk_index": chunk_index,
                            "object_path": _text(row.get("object_path")),
                            "exit_code": exit_code,
                            **_signal_receipt(exit_code),
                        }
                        semantic_stopped = True
                        break

                    chunk_resolved = _parse_probe_output(output, probe_qids)
                    for qid, node_id in chunk_resolved.items():
                        if qid not in resolved:
                            resolved[qid] = node_id
                            resolved_chunks[qid] = chunk_index

                    next_commit_position += 1
                    if all(qid in resolved for qid in requested):
                        semantic_stopped = True
                        break

                if semantic_stopped:
                    # Anything not yet started is above the serial stopping
                    # frontier and cannot affect semantic status.
                    for future in list(pending):
                        if future.cancel():
                            pending.pop(future)
                            chunks_cancelled_before_start += 1
                    # Completed speculative results are execution evidence only.
                    completed_buffer.clear()
                else:
                    submit_available()

                # Running futures that could not be cancelled still need to be
                # joined and receipted, but never semantically committed.
                if semantic_stopped and pending:
                    completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                    for future in completed:
                        pending.pop(future)
                        _position, row, _output, _probe_qids = future.result()
                        scanned.append(dict(row))

    scanned.sort(key=lambda row: int(row.get("chunk_index", 0)))
    unresolved = [qid for qid in requested if qid not in resolved]
    if failure is not None:
        status = (
            "engine_unavailable"
            if failure.get("failure_kind") == "runner_exception"
            else "engine_failed"
        )
    else:
        status = "complete" if not unresolved else "partial"

    cache_seed = {
        qid: {
            "zelph_node_id": resolved[qid],
            "node_of_name_chunk": resolved_chunks[qid],
        }
        for qid in sorted(resolved)
    }
    canonical_surface = {
        "status": status,
        "requested_qids": requested,
        "resolved_qids": dict(sorted(resolved.items())),
        "resolved_qid_chunks": dict(sorted(resolved_chunks.items())),
        "qid_route_cache_seed": cache_seed,
        "unresolved_qids": unresolved,
        "failure": failure,
        "language": language,
        "name_probe": "dot_node_non_creating",
        "node_id_success_surface": "marker_scoped_Node_ID",
        "nonzero_exit_means_no_match": False,
    }
    canonical_resolution_ref = "nat-zelph-hf-strict-canonical-resolution:" + canonical_sha256(
        canonical_surface
    )
    late_completions = sum(
        1
        for row in scanned
        if semantic_stopping_chunk is not None
        and int(row.get("chunk_index", 0)) > semantic_stopping_chunk
    )
    chunks_not_launched_after_stop = (
        max(0, len(chunks) - next_submit_position) if semantic_stopped else 0
    )

    payload_without_ref = {
        "schema_version": STRICT_PARTIAL_READ_SCHEMA_VERSION,
        **canonical_surface,
        "canonical_resolution_ref": canonical_resolution_ref,
        "chunks_scanned": scanned,
        "chunk_count_scanned": len(scanned),
        "clean_chunk_count": sum(1 for row in scanned if row.get("exit_code") == 0),
        "semantic_chunk_count_committed": committed_chunk_count,
        "available_node_of_name_chunk_count": len(
            node_of_name_chunks(manifest, language=language)
        ),
        "execution_strategy": "bounded_rate_limited_parallel_ordered_commit",
        "worker_budget": workers,
        "rate_limit_policy": {
            "shared_across_workers": True,
            "rps": getattr(limiter_cfg, "rps", None),
            "burst": getattr(limiter_cfg, "burst", None),
        },
        "peak_in_flight": peak_in_flight,
        "chunks_submitted": next_submit_position,
        "chunks_launched": chunks_launched,
        "chunks_cancelled_before_start": chunks_cancelled_before_start,
        "chunks_not_launched_after_stop": chunks_not_launched_after_stop,
        "late_completions": late_completions,
        "semantic_stopping_frontier_chunk": semantic_stopping_chunk,
        "network_performed": bool(chunks_launched),
        "route_index_required": False,
        "full_graph_loaded": False,
    }
    payload = dict(payload_without_ref)
    payload["partial_read_ref"] = "nat-zelph-hf-partial-read:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def _strict_evaluate(
    selector: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    headers: Mapping[str, Any],
) -> dict[str, Any]:
    preflight = _preflight_selector(selector)
    if isinstance(preflight, dict):
        return preflight

    scan = resolve_qids_via_hosted_partial_scan_strict(
        manifest, _text_list(selector.get("qids"))
    )
    status = _text(scan.get("status"))

    if status in {"engine_failed", "engine_unavailable"}:
        failure = scan.get("failure") or {}
        signal_name = _text(failure.get("signal_name"))
        detail = "Hosted Zelph nodeOfName probe failed before clean exhaustion."
        if signal_name:
            detail += f" Process terminated by {signal_name}."
        return {
            "executor_id": STRICT_EXECUTOR_ID,
            "execution_outcome": status,
            "executor_receipt": {
                "network_performed": bool(scan.get("network_performed")),
                "transport": "hf-object-fetch",
                "transport_status": "online_partial_scan_process_failed",
                "detail": detail,
                "partial_read": scan,
                "source_support_paid": False,
                "consumer_verification_performed": False,
                "semantic_promotion_performed": False,
                "edits_performed": False,
            },
            "outputs": {},
        }

    # Delegate successful / clean-no-match semantics to the existing selector,
    # but inject the already strict scan so it cannot rescan.
    return _evaluate_manifest(
        selector,
        manifest=manifest,
        headers=headers,
        partial_scan_resolver=lambda _manifest, _qids: scan,
        statement_fetcher=lambda qids, properties: fetch_live_wikidata_statement_payload(
            qids, properties
        ),
    )


def hosted_hf_selector_executor_strict(selector: Mapping[str, Any]) -> dict[str, Any]:
    """Production Nat executor with crash-aware partial-read semantics."""

    preflight = _preflight_selector(selector)
    if isinstance(preflight, dict):
        return preflight
    try:
        manifest, headers = _fetch_manifest_cached()
    except Exception as exc:
        return {
            "executor_id": STRICT_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": {
                "network_performed": True,
                "transport": "hf-object-fetch",
                "transport_status": "manifest_fetch_failed",
                "detail": f"{type(exc).__name__}: {exc}",
                "source_support_paid": False,
                "consumer_verification_performed": False,
                "semantic_promotion_performed": False,
                "edits_performed": False,
            },
            "outputs": {},
        }
    return _strict_evaluate(selector, manifest=manifest, headers=headers)


__all__ = [
    "STRICT_EXECUTOR_ID",
    "STRICT_PARTIAL_READ_SCHEMA_VERSION",
    "hosted_hf_selector_executor_strict",
    "resolve_qids_via_hosted_partial_scan_strict",
]
