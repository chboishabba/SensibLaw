from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from src.ontology.wikidata import (
    ENTITY_EXPORT_TEMPLATE,
    _fetch_entity_export_revision,
    _fetch_recent_revisions,
)
from src.policy.carriers.canonical import canonical_sha256


PARTIAL_READ_SCHEMA_VERSION = "sl.nat_zelph_hf_partial_read.v0_1"
RESOLVE_PATTERN = re.compile(r"SL_NAT_RESOLVE\|(Q\d+)\|\s*([0-9]+|nil|None|null)")


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
        # zelph/resolve is the public Janet resolver.  The sentinel keeps parsing
        # independent of ordinary REPL diagnostics and graph display output.
        lines.append(
            f'%(print "SL_NAT_RESOLVE|{qid}|" (zelph/resolve "{qid}"))'
        )
    lines.append(".exit")
    return "\n".join(lines) + "\n"


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


ReplRunner = Callable[[str, str], tuple[int, str]]


def resolve_qids_via_hosted_partial_scan(
    manifest: Mapping[str, Any],
    qids: Sequence[str],
    *,
    zelph_bin: str | None = None,
    language: str = "wikidata",
    max_chunks: int | None = None,
    timeout_seconds: float = 120.0,
    repl_runner: Callable[..., tuple[int, str]] | None = None,
) -> dict[str, Any]:
    """Resolve QID strings by scanning hosted v2 nodeOfName shards.

    This intentionally does not require a node-route sidecar.  It trades network
    bandwidth for progress while keeping the graph view partial: one nodeOfName
    shard is loaded at a time and the scan stops once every requested QID resolves.
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
            "unresolved_qids": requested,
            "chunks_scanned": [],
            "network_performed": False,
        }

    chunks = node_of_name_chunks(manifest, language=language)
    if max_chunks is not None:
        chunks = chunks[: max(0, int(max_chunks))]

    runner = repl_runner or _default_repl_runner
    resolved: dict[str, int] = {}
    scanned: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="sensiblaw-nat-hf-") as tmp:
        manifest_path = Path(tmp) / "wikidata.hf-v2.json"
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
                scanned.append(
                    {
                        "chunk_index": chunk_index,
                        "object_path": _text(chunk.get("objectPath")),
                        "exit_code": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            scanned.append(
                {
                    "chunk_index": chunk_index,
                    "object_path": _text(chunk.get("objectPath")),
                    "size_bytes": chunk.get("length"),
                    "exit_code": exit_code,
                }
            )
            for match in RESOLVE_PATTERN.finditer(output):
                qid, raw_node = match.groups()
                if raw_node.isdigit():
                    resolved[qid] = int(raw_node)

    unresolved = [qid for qid in requested if qid not in resolved]
    payload_without_ref = {
        "schema_version": PARTIAL_READ_SCHEMA_VERSION,
        "status": "complete" if not unresolved else "partial",
        "requested_qids": requested,
        "resolved_qids": dict(sorted(resolved.items())),
        "unresolved_qids": unresolved,
        "chunks_scanned": scanned,
        "chunk_count_scanned": len(scanned),
        "available_node_of_name_chunk_count": len(node_of_name_chunks(manifest, language=language)),
        "language": language,
        "network_performed": bool(scanned),
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

    Zelph's base graph is used for partial graph discovery/confirmation.  Exact
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
