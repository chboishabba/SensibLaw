#!/usr/bin/env python3
"""Normalize one failed exact-0008 trace into a comparison baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "sensiblaw.exact-0008-serial-baseline.v1"
PARSER_CHECKPOINT_SET_SCHEMA_VERSION = "sensiblaw.parser-checkpoint-set.v1"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return dict(value)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--parser-summary-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-typing-seconds", type=int, default=2 * 3600 + 35 * 60)
    parser.add_argument("--streaming-closure-seconds", type=int, default=3600 + 18 * 60)
    parser.add_argument("--other-seconds", type=int, default=7 * 60)
    parser.add_argument("--peak-rss-bytes", type=int, default=4_552_662_016)
    parser.add_argument("--processed-parser-tokens", type=int, default=279_532)
    parser.add_argument("--local-type-alternatives", type=int, default=254_554)
    parser.add_argument("--typed-meets", type=int, default=229_494)
    parser.add_argument("--refinements", type=int, default=214_479)
    parser.add_argument("--demands", type=int, default=305_275)
    parser.add_argument("--factor-scans", type=int, default=449_478)
    parser.add_argument("--output-nodes", type=int, default=251_426)
    return parser.parse_args()


def _parser_coverage(root: Path) -> dict[str, Any]:
    paths = tuple(sorted(root.rglob("*.summary.json")))
    if not paths:
        raise ValueError(f"no parser summaries found under {root}")
    summaries = [_json(path) for path in paths]
    rows = sorted(
        (dict(summary.get("fibre") or {}) for summary in summaries),
        key=lambda row: int(row.get("sequence_no", -1)),
    )
    document_refs = {str(row.get("document_ref") or "") for row in rows}
    contract_refs = {str(summary.get("contract_ref") or "") for summary in summaries}
    if len(document_refs) != 1 or "" in document_refs:
        raise ValueError("parser summaries disagree on document identity")
    if len(contract_refs) != 1 or "" in contract_refs:
        raise ValueError("parser summaries disagree on parser contract")
    if [int(row["sequence_no"]) for row in rows] != list(range(len(rows))):
        raise ValueError("parser fibre sequence is incomplete")
    for left, right in zip(rows, rows[1:], strict=False):
        if int(left["owner_end"]) != int(right["owner_start"]):
            raise ValueError("parser owner coverage is not contiguous and exact")
    if int(rows[0]["owner_start"]) != 0:
        raise ValueError("parser owner coverage does not begin at zero")

    document_ref = next(iter(document_refs))
    parser_contract_ref = next(iter(contract_refs))
    identity_rows = [
        {
            "sequence_no": int(row["sequence_no"]),
            "fibre_ref": str(row["fibre_ref"]),
            "owner_start": int(row["owner_start"]),
            "owner_end": int(row["owner_end"]),
            "context_start": int(row["context_start"]),
            "context_end": int(row["context_end"]),
            "text_sha256": str(row.get("text_sha256") or ""),
        }
        for row in rows
    ]
    checkpoint_identity = {
        "schema_version": PARSER_CHECKPOINT_SET_SCHEMA_VERSION,
        "document_ref": document_ref,
        "parser_contract_ref": parser_contract_ref,
        "fibres": identity_rows,
    }
    return {
        "document_ref": document_ref,
        "parser_contract_ref": parser_contract_ref,
        "checkpoint_identity_schema_version": PARSER_CHECKPOINT_SET_SCHEMA_VERSION,
        "checkpoint_digest": _canonical_sha256(checkpoint_identity),
        "checkpoint_refs": [str(row["fibre_ref"]) for row in rows],
        "fibre_text_sha256": [str(row.get("text_sha256") or "") for row in rows],
        "fibre_identity_rows": identity_rows,
        "fibre_count": len(rows),
        "canonical_character_count": int(rows[-1]["owner_end"]),
        "owned_sentence_count": sum(
            int(summary.get("owned_sentence_count") or 0) for summary in summaries
        ),
        "owned_token_count": sum(
            int(summary.get("owned_token_count") or 0) for summary in summaries
        ),
        "context_token_count": sum(
            int((summary.get("counts") or {}).get("tokens") or 0)
            for summary in summaries
        ),
        "exact_owner_coverage": True,
        "context_overlap_is_execution_only": True,
    }


def build_baseline(args: argparse.Namespace) -> dict[str, Any]:
    state = _json(args.state)
    coverage = _parser_coverage(args.parser_summary_root)
    if int(state.get("completed_document_count") or 0) != 0:
        raise ValueError("failed serial baseline unexpectedly completed a document")
    failures = tuple(str(value) for value in state.get("failure_refs") or ())
    if not failures:
        raise ValueError("failed serial baseline requires a failure receipt")
    documents = dict(state.get("documents") or {})
    document_state = documents.get(coverage["document_ref"])
    if not isinstance(document_state, Mapping) or document_state.get("state") != "failed":
        raise ValueError("parser checkpoint document is not the failed compiler document")
    configuration = {
        "worker_budget": int(state.get("worker_budget") or 0),
        "document_workers": int(state.get("document_workers") or 0),
        "parser_workers": int(state.get("parser_workers") or 0),
        "closure_workers": int(state.get("closure_workers") or 0),
        "owner_partitions": int(state.get("owner_partitions") or 0),
        "parser_limit_chars": int(state.get("parser_limit_chars") or 0),
        "parser_target_chars": int(state.get("parser_target_chars") or 0),
        "parser_overlap_chars": int(state.get("parser_overlap_chars") or 0),
    }
    serial_keys = (
        "worker_budget",
        "document_workers",
        "parser_workers",
        "closure_workers",
        "owner_partitions",
    )
    if any(configuration[key] != 1 for key in serial_keys):
        raise ValueError("baseline is not the expected one-worker serial trace")

    stage_timeline = [
        {
            "stage": "local_typing_diagnostics",
            "elapsed_seconds": args.local_typing_seconds,
            "share_of_estimated_runtime": (
                args.local_typing_seconds
                / (
                    args.local_typing_seconds
                    + args.streaming_closure_seconds
                    + args.other_seconds
                )
            ),
            "measurement_quality": "approximate_from_failed_trace",
            "kernel_breakdown_available": False,
        },
        {
            "stage": "streaming_closure",
            "elapsed_seconds": args.streaming_closure_seconds,
            "share_of_estimated_runtime": (
                args.streaming_closure_seconds
                / (
                    args.local_typing_seconds
                    + args.streaming_closure_seconds
                    + args.other_seconds
                )
            ),
            "measurement_quality": "approximate_from_failed_trace",
            "kernel_breakdown_available": False,
        },
        {
            "stage": "all_other_stages",
            "elapsed_seconds": args.other_seconds,
            "share_of_estimated_runtime": (
                args.other_seconds
                / (
                    args.local_typing_seconds
                    + args.streaming_closure_seconds
                    + args.other_seconds
                )
            ),
            "measurement_quality": "approximate_from_failed_trace",
            "kernel_breakdown_available": False,
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "document_ref": coverage["document_ref"],
        "compiler_contract_ref": str(state.get("document_executor_contract_ref") or ""),
        "corpus_ref": str(state.get("corpus_ref") or ""),
        "manifest_sha256": str(state.get("manifest_sha256") or ""),
        "configuration": configuration,
        "parser_checkpoints": coverage,
        "stage_timeline": stage_timeline,
        "runtime": {
            "measurement_quality": "approximate_from_failed_trace",
            "local_typing_diagnostics_seconds": args.local_typing_seconds,
            "streaming_closure_seconds": args.streaming_closure_seconds,
            "other_stages_seconds": args.other_seconds,
            "estimated_total_seconds": (
                args.local_typing_seconds
                + args.streaming_closure_seconds
                + args.other_seconds
            ),
            "observed_peak_rss_bytes": args.peak_rss_bytes,
        },
        "semantic_counts": {
            "measurement_quality": "reported_by_failed_compiler_trace",
            "processed_parser_tokens": args.processed_parser_tokens,
            "local_type_alternatives": args.local_type_alternatives,
            "typed_meets": args.typed_meets,
            "refinements": args.refinements,
            "demands": args.demands,
            "factor_scans": args.factor_scans,
            "output_nodes": args.output_nodes,
        },
        "failure": {
            "failure_refs": list(failures),
            "document_state": dict(document_state),
            "completed_document_count": 0,
            "compiler_publication_state": "not_started",
            "sql_publication_audit": "not_asserted_by_this_file",
        },
        "comparison_role": "serial_failed_trace_baseline",
        "semantic_output_identity": None,
        "publication_identity": None,
    }


def main() -> int:
    args = _parse_args()
    payload = build_baseline(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
