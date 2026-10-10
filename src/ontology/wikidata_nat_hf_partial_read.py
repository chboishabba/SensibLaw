from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from src.ontology.wikidata import (
    ENTITY_EXPORT_TEMPLATE,
    _fetch_entity_export_revision,
    _fetch_recent_revisions,
)
from src.policy.carriers.canonical import canonical_sha256
from src.sources.rate_limit import RateLimit, TokenBucketRateLimiter


PARTIAL_READ_SCHEMA_VERSION = "sl.nat_zelph_hf_partial_read.v0_2"
PROBE_MARKER_PATTERN = re.compile(r"SL_NAT_PROBE\|(Q\d+)\|")
# `.node <name>` always prints `Node ID: N` for a successful single-node
# result.  It prepends `Resolved to node ID: N` only when its forward
# nameOfNode lookup can also prove that the argument was resolved by name.
# Our bounded scan intentionally loads nodeOfName only, so the plain line is
# the authoritative success surface in that partial view.
NODE_ID_PATTERN = re.compile(r"(?:Resolved to node ID|Node ID):\s*([0-9]+)")


class RateLimiter(Protocol):
    """Minimal admission interface shared with SensibLaw source adapters."""

    def acquire(self, tokens: float = 1.0) -> None: ...


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def node_of_name_chunks(
    manifest: Mapping[str, Any], *, language: str = "wikidata"
) -> list[dict[str, Any]]:
    section = (manifest.get("sections") or {}).get("nodeOfName") or {}
    chunks = section.get("chunks") or []
    result: list[dict[str, Any]] = []
    for raw in chunks:
        if not isinstance(raw, Mapping):
            continue
        lang = _text(raw.get("lang"))
        if lang and lang != language:
            continue
        if raw.get("chunkIndex") is None:
            continue
        result.append(dict(raw))
    result.sort(key=lambda row: int(row.get("chunkIndex", 0)))
    return result


def _resolve_probe_payload(
    *, manifest_path: Path, chunk_index: int, qids: Sequence[str], language: str
) -> str:
    lines = [
        (
            f".load-partial {manifest_path} left=none right=none "
            f"nameOfNode=none nodeOfName={chunk_index} manifest={manifest_path}"
        ),
        f".lang {language}",
    ]
    for qid in qids:
        # IMPORTANT: do not use zelph/resolve here. Upstream documents resolve
        # as creating a node when the name is absent. `.node <name>` uses the
        # non-destructive lookup path. In a reverse-map-only partial view it may
        # print just `Node ID: N`, because nameOfNode was deliberately omitted.
        lines.append(f'%(print "SL_NAT_PROBE|{qid}|")')
        lines.append(f".node {qid}")
    # Current upstream registers `.quit`; `.exit` is not a command in 0.9.9-dev.
    lines.append(".quit")
    return "\n".join(lines) + "\n"


def _parse_probe_output(output: str, requested_qids: Sequence[str]) -> dict[str, int]:
    requested = set(requested_qids)
    resolved: dict[str, int] = {}
    active_qid: str | None = None
    for line in output.splitlines():
        marker = PROBE_MARKER_PATTERN.search(line)
        if marker:
            active_qid = marker.group(1)
            continue
        if active_qid is None or active_qid not in requested:
            continue
        node_match = NODE_ID_PATTERN.search(line)
        if node_match:
            resolved[active_qid] = int(node_match.group(1))
            active_qid = None
            continue
        # An absent name is intentionally not a negative-evidence result. The
        # command reports it as an error/diagnostic; the next marker starts the
        # next probe. No node is created by this path.
    return resolved


def _default_repl_runner(
    zelph_bin: str, payload: str, *, timeout_seconds: float
) -> tuple[int, str]:
    proc = subprocess.run(
        [zelph_bin],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        timeout=max(1.0, float(timeout_seconds)),
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def resolve_qids_via_hosted_partial_scan(
    manifest: Mapping[str, Any],
    qids: Sequence[str],
    *,
    zelph_bin: str | None = None,
    language: str = "wikidata",
    max_chunks: int | None = None,
    timeout_seconds: float = 120.0,
    repl_runner: Callable[..., tuple[int, str]] | None = None,
    worker_budget: int = 4,
    rate_limiter: RateLimiter | None = None,
) -> dict[str, Any]:
    """Resolve QID strings by scanning hosted v2 nodeOfName shards.

    The scan uses a bounded sliding window of chunk subprocesses. Every worker
    must acquire from one shared SensibLaw token-bucket authority before the
    subprocess starts, so increasing worker count cannot multiply request rate.

    Semantic reduction remains equivalent to the old sorted serial scan: for a
    QID observed in more than one admitted chunk, the lowest chunk index wins.
    Once all QIDs resolve, we still wait for any already-running chunk at or
    below the current serial stopping frontier; only higher-index work may be
    cancelled/ignored for semantic reduction. Thus completion order never owns
    QID identity.

    This intentionally does not require a node-route sidecar. It trades network
    bandwidth for progress while keeping the graph view partial and read-only.
    """

    requested = _text_list(qids)
    if not requested:
        raise ValueError("partial QID scan requires at least one QID")

    binary = _text(zelph_bin or os.environ.get("ZELPH_BIN") or shutil.which("zelph"))
    if not binary:
        return {
            "schema_version": PARTIAL_READ_SCHEMA_VERSION,
            "status": "zelph_binary_unavailable",
            "requested_qids": requested,
            "resolved_qids": {},
            "resolved_qid_chunks": {},
            "qid_route_cache_seed": {},
            "unresolved_qids": requested,
            "chunks_scanned": [],
            "execution_strategy": "bounded_rate_limited_parallel",
            "worker_budget": max(1, int(worker_budget)),
            "network_performed": False,
        }

    chunks = node_of_name_chunks(manifest, language=language)
    if max_chunks is not None:
        chunks = chunks[: max(0, int(max_chunks))]

    workers = max(1, int(worker_budget))
    limiter = rate_limiter or TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1))
    limiter_cfg = getattr(limiter, "cfg", None)
    runner = repl_runner or _default_repl_runner

    resolved: dict[str, int] = {}
    resolved_chunks: dict[str, int] = {}
    scanned: list[dict[str, Any]] = []

    stats_lock = Lock()
    active_runner_count = 0
    peak_in_flight = 0
    chunks_launched = 0

    with tempfile.TemporaryDirectory(prefix="sensiblaw-nat-hf-") as tmp:
        manifest_path = Path(tmp) / "wikidata.hf-v2.json"
        manifest_path.write_text(
            json.dumps(dict(manifest), indent=2, sort_keys=True), encoding="utf-8"
        )

        def run_chunk(
            chunk: Mapping[str, Any], probe_qids: tuple[str, ...]
        ) -> tuple[dict[str, Any], dict[str, int]]:
            nonlocal active_runner_count, peak_in_flight, chunks_launched
            chunk_index = int(chunk["chunkIndex"])
            try:
                limiter.acquire()
            except Exception as exc:
                return (
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "exit_code": None,
                        "error": f"rate admission failed: {type(exc).__name__}: {exc}",
                    },
                    {},
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
                row = {
                    "chunk_index": chunk_index,
                    "object_path": _text(chunk.get("objectPath")),
                    "size_bytes": chunk.get("length"),
                    "exit_code": exit_code,
                }
                return row, _parse_probe_output(output, probe_qids)
            except Exception as exc:
                return (
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "exit_code": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    {},
                )
            finally:
                with stats_lock:
                    active_runner_count -= 1

        next_chunk = 0
        stopped_submitting = False
        chunks_cancelled_before_start = 0
        pending: dict[Future[tuple[dict[str, Any], dict[str, int]]], int] = {}

        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="sensiblaw-nat-hf"
        ) as pool:

            def submit_available() -> None:
                nonlocal next_chunk
                while (
                    not stopped_submitting
                    and len(pending) < workers
                    and next_chunk < len(chunks)
                ):
                    remaining = tuple(qid for qid in requested if qid not in resolved)
                    if not remaining:
                        return
                    chunk = chunks[next_chunk]
                    next_chunk += 1
                    chunk_index = int(chunk["chunkIndex"])
                    pending[pool.submit(run_chunk, chunk, remaining)] = chunk_index

            submit_available()
            while pending:
                completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                # Completion timing must not become semantic authority. Reduce a
                # simultaneous completion batch in canonical chunk-index order.
                completed_ordered = sorted(completed, key=lambda future: pending[future])
                for future in completed_ordered:
                    chunk_index = pending.pop(future)
                    row, chunk_resolved = future.result()
                    scanned.append(row)
                    for qid, node_id in chunk_resolved.items():
                        previous_chunk = resolved_chunks.get(qid)
                        if previous_chunk is None or chunk_index < previous_chunk:
                            resolved[qid] = node_id
                            resolved_chunks[qid] = chunk_index

                all_resolved = all(qid in resolved for qid in requested)
                if all_resolved:
                    stopped_submitting = True
                    serial_frontier = max(resolved_chunks[qid] for qid in requested)
                    # A task above the current serial frontier can no longer
                    # affect the canonical result. Cancel it if it has not begun.
                    for future, chunk_index in list(pending.items()):
                        if chunk_index > serial_frontier and future.cancel():
                            pending.pop(future)
                            chunks_cancelled_before_start += 1
                else:
                    submit_available()

    scanned.sort(key=lambda row: int(row.get("chunk_index", 0)))
    unresolved = [qid for qid in requested if qid not in resolved]
    cache_seed = {
        qid: {
            "zelph_node_id": resolved[qid],
            "node_of_name_chunk": resolved_chunks[qid],
        }
        for qid in sorted(resolved)
    }

    serial_frontier = (
        max(resolved_chunks[qid] for qid in requested) if not unresolved else None
    )
    late_completions = (
        sum(
            1
            for row in scanned
            if int(row.get("chunk_index", 0)) > int(serial_frontier)
        )
        if serial_frontier is not None
        else 0
    )
    chunks_not_launched_after_resolution = (
        max(0, len(chunks) - next_chunk) if stopped_submitting else 0
    )

    canonical_surface = {
        "requested_qids": requested,
        "resolved_qids": dict(sorted(resolved.items())),
        "resolved_qid_chunks": dict(sorted(resolved_chunks.items())),
        "qid_route_cache_seed": cache_seed,
        "unresolved_qids": unresolved,
        "language": language,
        "name_probe": "dot_node_non_creating",
        "node_id_success_surface": "marker_scoped_Node_ID",
    }
    canonical_resolution_ref = "nat-zelph-hf-canonical-resolution:" + canonical_sha256(
        canonical_surface
    )

    payload_without_ref = {
        "schema_version": PARTIAL_READ_SCHEMA_VERSION,
        "status": "complete" if not unresolved else "partial",
        **canonical_surface,
        "canonical_resolution_ref": canonical_resolution_ref,
        "chunks_scanned": scanned,
        "chunk_count_scanned": len(scanned),
        "available_node_of_name_chunk_count": len(
            node_of_name_chunks(manifest, language=language)
        ),
        "execution_strategy": "bounded_rate_limited_parallel",
        "worker_budget": workers,
        "rate_limit_policy": {
            "shared_across_workers": True,
            "rps": getattr(limiter_cfg, "rps", None),
            "burst": getattr(limiter_cfg, "burst", None),
        },
        "peak_in_flight": peak_in_flight,
        "chunks_submitted": next_chunk,
        "chunks_launched": chunks_launched,
        "chunks_completed": len(scanned),
        "chunks_cancelled_before_start": chunks_cancelled_before_start,
        "chunks_not_launched_after_resolution": chunks_not_launched_after_resolution,
        "late_completions": late_completions,
        "serial_stopping_frontier_chunk": serial_frontier,
        "network_performed": bool(chunks_launched),
        "route_index_required": False,
        "full_graph_loaded": False,
    }
    payload = dict(payload_without_ref)
    payload["partial_read_ref"] = "nat-zelph-hf-partial-read:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def _statement_id(statement: Mapping[str, Any], fallback: str) -> str:
    return _text(statement.get("id")) or fallback


def fetch_live_wikidata_statement_payload(
    qids: Sequence[str],
    properties: Sequence[str],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Fetch the rich Wikidata statement layer for already-bounded QIDs.

    Zelph's graph is used for partial graph discovery/confirmation. Exact
    qualifier/reference snaks and revision lineage remain source-owned by the
    Wikidata entity export and are fetched from SensibLaw's existing live path.
    """

    requested_qids = _text_list(qids)
    requested_properties = set(_text_list(properties))
    statement_snapshot: dict[str, Any] = {}
    qualifier_snaks: dict[str, Any] = {}
    reference_snaks: dict[str, Any] = {}
    lineage: dict[str, Any] = {}

    for qid in requested_qids:
        revisions = _fetch_recent_revisions(
            qid, revision_limit=2, timeout_seconds=timeout_seconds
        )
        if not revisions:
            raise ValueError(f"no live Wikidata revision found for {qid}")
        latest = revisions[0]
        revid = int(latest["revid"])
        entity_export = _fetch_entity_export_revision(
            qid, revid, timeout_seconds=timeout_seconds
        )
        entity = (entity_export.get("entities") or {}).get(qid) or {}
        claims = entity.get("claims") or {}

        selected_claims: dict[str, Any] = {}
        qid_qualifiers: dict[str, Any] = {}
        qid_references: dict[str, Any] = {}
        for prop in sorted(requested_properties):
            statements = claims.get(prop) or []
            if not statements:
                continue
            selected_claims[prop] = statements
            for index, raw_statement in enumerate(statements):
                if not isinstance(raw_statement, Mapping):
                    continue
                sid = _statement_id(raw_statement, f"{qid}|{prop}|{index}")
                qualifiers = raw_statement.get("qualifiers") or {}
                references = raw_statement.get("references") or []
                qid_qualifiers[sid] = qualifiers
                qid_references[sid] = [
                    dict(ref.get("snaks") or {})
                    for ref in references
                    if isinstance(ref, Mapping)
                ]

        statement_snapshot[qid] = {
            "revid": revid,
            "timestamp": _text(latest.get("timestamp")),
            "claims": selected_claims,
        }
        qualifier_snaks[qid] = qid_qualifiers
        reference_snaks[qid] = qid_references
        lineage[qid] = {
            "revid": revid,
            "timestamp": _text(latest.get("timestamp")),
            "entity_export_url": ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=revid),
        }

    outputs_without_address = {
        "statement_snapshot": statement_snapshot,
        "qualifier_snaks": qualifier_snaks,
        "reference_snaks": reference_snaks,
        "source_revision_lineage": lineage,
    }
    outputs = dict(outputs_without_address)
    outputs["content_address"] = "sha256:" + canonical_sha256(outputs_without_address)
    return outputs


__all__ = [
    "PARTIAL_READ_SCHEMA_VERSION",
    "fetch_live_wikidata_statement_payload",
    "node_of_name_chunks",
    "resolve_qids_via_hosted_partial_scan",
]
