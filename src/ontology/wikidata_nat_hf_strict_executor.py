from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.ontology.wikidata_nat_hf_partial_read import (
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
) -> dict[str, Any]:
    """Hosted nodeOfName scan with fail-closed process semantics.

    Clean exhaustion is the only route to ``status=partial``. Any runner
    exception is ``engine_unavailable``; any non-zero Zelph exit is
    ``engine_failed`` and stops the scan immediately. In particular a SIGSEGV
    can never be reinterpreted as a QID no-match.
    """

    requested = _text_list(qids)
    if not requested:
        raise ValueError("strict partial QID scan requires at least one QID")

    binary = _text(zelph_bin or os.environ.get("ZELPH_BIN") or shutil.which("zelph"))
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
            "network_performed": False,
            "route_index_required": False,
            "full_graph_loaded": False,
            "name_probe": "dot_node_non_creating",
            "nonzero_exit_means_no_match": False,
        }

    chunks = node_of_name_chunks(manifest, language=language)
    if max_chunks is not None:
        chunks = chunks[: max(0, int(max_chunks))]

    runner = repl_runner or _default_repl_runner
    resolved: dict[str, int] = {}
    resolved_chunks: dict[str, int] = {}
    scanned: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="sensiblaw-nat-hf-strict-") as tmp:
        manifest_path = Path(tmp) / "wikidata.hf-v2.json"
        import json

        manifest_path.write_text(
            json.dumps(dict(manifest), indent=2, sort_keys=True), encoding="utf-8"
        )

        for chunk in chunks:
            remaining = [qid for qid in requested if qid not in resolved]
            if not remaining:
                break

            chunk_index = int(chunk["chunkIndex"])
            payload = _resolve_probe_payload(
                manifest_path=manifest_path,
                chunk_index=chunk_index,
                qids=remaining,
                language=language,
            )
            try:
                exit_code, output = runner(
                    binary, payload, timeout_seconds=timeout_seconds
                )
            except Exception as exc:
                failure = {
                    "failure_kind": "runner_exception",
                    "exception_type": type(exc).__name__,
                    "exception_detail": str(exc),
                    "chunk_index": chunk_index,
                    "object_path": _text(chunk.get("objectPath")),
                }
                scanned.append(
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "size_bytes": chunk.get("length"),
                        "exit_code": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                break

            scan_row = {
                "chunk_index": chunk_index,
                "object_path": _text(chunk.get("objectPath")),
                "size_bytes": chunk.get("length"),
                "exit_code": int(exit_code),
            }
            scanned.append(scan_row)

            if exit_code != 0:
                failure = {
                    "failure_kind": "zelph_process_failed",
                    "chunk_index": chunk_index,
                    "object_path": _text(chunk.get("objectPath")),
                    "exit_code": int(exit_code),
                    **_signal_receipt(int(exit_code)),
                }
                break

            chunk_resolved = _parse_probe_output(output, remaining)
            for qid, node_id in chunk_resolved.items():
                resolved[qid] = node_id
                resolved_chunks[qid] = chunk_index

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
    payload_without_ref = {
        "schema_version": STRICT_PARTIAL_READ_SCHEMA_VERSION,
        "status": status,
        "requested_qids": requested,
        "resolved_qids": dict(sorted(resolved.items())),
        "resolved_qid_chunks": dict(sorted(resolved_chunks.items())),
        "qid_route_cache_seed": cache_seed,
        "unresolved_qids": unresolved,
        "chunks_scanned": scanned,
        "chunk_count_scanned": len(scanned),
        "clean_chunk_count": sum(1 for row in scanned if row.get("exit_code") == 0),
        "available_node_of_name_chunk_count": len(
            node_of_name_chunks(manifest, language=language)
        ),
        "failure": failure,
        "language": language,
        "network_performed": bool(scanned),
        "route_index_required": False,
        "full_graph_loaded": False,
        "name_probe": "dot_node_non_creating",
        "node_id_success_surface": "marker_scoped_Node_ID",
        "nonzero_exit_means_no_match": False,
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
