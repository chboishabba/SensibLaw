"""Process-isolated mention licensing over one canonical document carrier.

Workers scan owned token ranges and sentence-local proper-name runs, returning
additive candidate and suppression deltas.  The document owner normalizes token
intervals, applies license priority, assigns stable mention references and hashes
one authoritative carrier.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from time import time_ns
from typing import Any, Callable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.policy import entity_resolution as legacy


DOCUMENT_GRAPH_MENTION_CONTRACT = "document-graph-mention-licensing:v0_1"


def _worker_budget(parsed_document: Mapping[str, Any] | None) -> int:
    override = os.getenv("SENSIBLAW_DOCUMENT_WORKERS", "").strip()
    if override:
        try:
            return max(1, min(32, int(override)))
        except ValueError:
            pass
    receipt = (parsed_document or {}).get("parser_receipt") or {}
    if isinstance(receipt, Mapping):
        raw = receipt.get("worker_count") or receipt.get("granted_workers") or 1
        try:
            return max(1, min(32, int(raw)))
        except (TypeError, ValueError):
            pass
    return 1


def _token_partitions(
    token_rows: Sequence[tuple[str, int, int]],
    *,
    worker_budget: int,
    partitions_per_worker: int,
) -> tuple[tuple[int, int], ...]:
    if not token_rows:
        return ()
    desired = min(
        len(token_rows),
        max(1, worker_budget * max(1, partitions_per_worker)),
    )
    size = max(1, (len(token_rows) + desired - 1) // desired)
    return tuple(
        (start, min(len(token_rows), start + size))
        for start in range(0, len(token_rows), size)
    )


def _sentence_owner_index(
    sentence: Mapping[str, Any],
    *,
    token_starts: Sequence[int],
    token_count: int,
) -> int:
    tokens = tuple(sentence.get("tokens") or ())
    if tokens:
        start_char = int(tokens[0].get("start", 0))
    else:
        start_char = int(sentence.get("start", sentence.get("start_char", 0)))
    return min(max(0, bisect_left(token_starts, start_char)), max(0, token_count - 1))


def _mention_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    started_ns = time_ns()
    proposed: list[tuple[int, int, str, tuple[str, ...], tuple[str, ...]]] = []
    suppressed: list[tuple[int, int, str]] = []

    for row in payload["tokens"]:
        token_index = int(row["token_index"])
        token = str(row["token"])
        start_char = int(row["start_char"])
        end_char = int(row["end_char"])
        annotation = row.get("annotation")
        normalized = token.strip().lower()
        if not legacy._is_lexical_token(token):
            suppressed.append((token_index, token_index + 1, "punctuation_or_symbol"))
            continue
        if normalized in legacy._STRUCTURAL_LEXEMES:
            suppressed.append((token_index, token_index + 1, "structural_lexeme"))
            continue
        proposed.append(
            (
                start_char,
                end_char,
                "lexical_token",
                legacy._lexical_expected_kinds(annotation),
                legacy._local_types(annotation),
            )
        )
        pos = str((annotation or {}).get("pos") or "")
        if pos == "NUM":
            proposed.append(
                (
                    start_char,
                    end_char,
                    "numeric_literal",
                    ("event_type", "literal"),
                    ("numeric_expression",),
                )
            )
        if pos in {"VERB", "AUX"}:
            proposed.append(
                (
                    start_char,
                    end_char,
                    "eventuality_annotation",
                    ("event_type", "property"),
                    ("linguistic_eventuality",),
                )
            )

    for sentence in payload["sentences"]:
        run: list[Mapping[str, Any]] = []
        for token in sentence.get("tokens") or ():
            if str(token.get("pos") or "") == "PROPN":
                run.append(token)
                continue
            if run:
                proposed.append(
                    (
                        int(run[0]["start"]),
                        int(run[-1]["end"]),
                        "named_entity_shape",
                        ("document_local", "instance"),
                        ("proper_name_phrase",),
                    )
                )
                run = []
        if run:
            proposed.append(
                (
                    int(run[0]["start"]),
                    int(run[-1]["end"]),
                    "named_entity_shape",
                    ("document_local", "instance"),
                    ("proper_name_phrase",),
                )
            )

    ended_ns = time_ns()
    return {
        "sequence_no": int(payload["sequence_no"]),
        "start_token": int(payload["start_token"]),
        "end_token": int(payload["end_token"]),
        "proposed": proposed,
        "suppressed": suppressed,
        "worker_pid": os.getpid(),
        "started_ns": started_ns,
        "ended_ns": ended_ns,
        "compute_ms": max(0, (ended_ns - started_ns) // 1_000_000),
    }


def _peak_active_workers(results: Sequence[Mapping[str, Any]]) -> int:
    events: list[tuple[int, int]] = []
    for result in results:
        events.append((int(result["started_ns"]), 1))
        events.append((int(result["ended_ns"]), -1))
    active = 0
    peak = 0
    for _timestamp, delta in sorted(events, key=lambda row: (row[0], -row[1])):
        active += delta
        peak = max(peak, active)
    return peak


def _semantic_payload(carrier: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: carrier[key]
        for key in (
            "schema_version",
            "authority",
            "source_ref",
            "document_ref",
            "canonical_text_sha256",
            "lattice",
            "mentions",
            "licenses",
            "suppressed_spans",
            "carrier_ref",
            "resolution_effect",
            "promotion_effect",
            "execution_effect",
            "summary",
        )
    }


def build_document_mention_licensing_carrier(
    *,
    canonical_text: str,
    source_ref: str,
    document_ref: str,
    context_refs: Sequence[str] = (),
    parsed_document: Mapping[str, Any] | None = None,
    tokens: Sequence[tuple[str, int, int]] | None = None,
    progress_observer: Callable[[Mapping[str, Any]], None] | None = None,
    worker_budget: int | None = None,
    partitions_per_worker: int = 2,
    min_parallel_tokens: int = 2_048,
    verify_serial: bool = False,
) -> dict[str, Any]:
    """Build the legacy mention carrier from process-local scan deltas."""

    text = str(canonical_text)
    if not text:
        raise ValueError("mention licensing requires canonical_text")
    source = legacy._text(source_ref, "source_ref")
    document = legacy._text(document_ref, "document_ref")
    canonical_context_refs = legacy._refs(context_refs)
    token_rows = tuple(tokens) if tokens is not None else tuple(
        legacy.tokenize_canonical_with_spans(text)
    )
    parsed = (
        dict(parsed_document)
        if parsed_document is not None
        else legacy.parse_canonical_text(text)
    )
    if parsed_document is not None and str(parsed.get("text") or "") != text:
        raise ValueError("parsed_document text must equal canonical_text")

    requested_workers = worker_budget or _worker_budget(parsed)
    if requested_workers <= 1 or len(token_rows) < min_parallel_tokens:
        serial = legacy.build_mention_licensing_carrier(
            canonical_text=text,
            source_ref=source,
            document_ref=document,
            context_refs=canonical_context_refs,
            parsed_document=parsed,
            tokens=token_rows,
            progress_observer=progress_observer,
        )
        fingerprint = canonical_sha256(_semantic_payload(serial))
        return {
            **serial,
            "licensing_execution_receipt": {
                "contract_ref": DOCUMENT_GRAPH_MENTION_CONTRACT,
                "execution_mode": "serial",
                "requested_workers": requested_workers,
                "granted_workers": 1,
                "peak_active_workers": 1,
                "partition_count": 1,
                "semantic_fingerprint": fingerprint,
                "serial_fingerprint": fingerprint,
                "serial_parallel_parity": True,
                "budget_invariant_satisfied": True,
                "authority": "execution_receipt_only",
            },
        }

    annotations = legacy._annotation_by_span(parsed)
    token_starts = [row[1] for row in token_rows]
    partitions = _token_partitions(
        token_rows,
        worker_budget=requested_workers,
        partitions_per_worker=partitions_per_worker,
    )
    granted_workers = min(requested_workers, len(partitions))
    sentences_by_partition: list[list[Mapping[str, Any]]] = [
        [] for _partition in partitions
    ]
    for sentence in parsed.get("sents") or ():
        if not isinstance(sentence, Mapping):
            continue
        owner_index = _sentence_owner_index(
            sentence,
            token_starts=token_starts,
            token_count=len(token_rows),
        )
        partition_index = next(
            (
                index
                for index, (start, end) in enumerate(partitions)
                if start <= owner_index < end
            ),
            len(partitions) - 1,
        )
        sentences_by_partition[partition_index].append(sentence)

    execution_started_ns = time_ns()
    results: list[dict[str, Any]] = []
    completed_tokens = 0
    proposed_seen = 0
    with ProcessPoolExecutor(max_workers=granted_workers) as executor:
        futures = {}
        for sequence_no, ((start_token, end_token), sentences) in enumerate(
            zip(partitions, sentences_by_partition, strict=True)
        ):
            payload = {
                "sequence_no": sequence_no,
                "start_token": start_token,
                "end_token": end_token,
                "tokens": [
                    {
                        "token_index": token_index,
                        "token": token_rows[token_index][0],
                        "start_char": token_rows[token_index][1],
                        "end_char": token_rows[token_index][2],
                        "annotation": annotations.get(
                            (token_rows[token_index][1], token_rows[token_index][2])
                        ),
                    }
                    for token_index in range(start_token, end_token)
                ],
                "sentences": tuple(sentences),
            }
            futures[executor.submit(_mention_worker, payload)] = (start_token, end_token)
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            start_token, end_token = futures[future]
            completed_tokens += end_token - start_token
            proposed_seen += len(result["proposed"])
            if progress_observer is not None:
                progress_observer(
                    {
                        "tokens_scanned": completed_tokens,
                        "mentions_considered": proposed_seen,
                        "mentions_licensed": 0,
                        "forms_derived": 0,
                        "recurrences_derived": 0,
                    }
                )

    owner_merge_started_ns = time_ns()
    proposed: dict[
        tuple[int, int], list[tuple[str, tuple[str, ...], tuple[str, ...]]]
    ] = {}
    suppressed: list[legacy.SuppressedSpan] = []
    for result in sorted(results, key=lambda row: int(row["sequence_no"])):
        for start_char, end_char, kind, expected, local_types in result["proposed"]:
            proposed.setdefault((int(start_char), int(end_char)), []).append(
                (str(kind), tuple(expected), tuple(local_types))
            )
        suppressed.extend(
            legacy.SuppressedSpan(int(start), int(end), str(reason))
            for start, end, reason in result["suppressed"]
        )

    token_ends = [row[2] for row in token_rows]
    exact_intervals = {
        (start, end): (index, index + 1)
        for index, (_token, start, end) in enumerate(token_rows)
    }

    def token_interval(start_char: int, end_char: int) -> tuple[int, int] | None:
        exact = exact_intervals.get((start_char, end_char))
        if exact is not None:
            return exact
        start_index = bisect_left(token_starts, start_char)
        end_index = bisect_right(token_ends, end_char)
        if start_index >= end_index:
            return None
        if token_starts[start_index] < start_char or token_ends[end_index - 1] > end_char:
            return None
        return start_index, end_index

    normalized_proposed: dict[
        tuple[int, int], list[tuple[str, tuple[str, ...], tuple[str, ...]]]
    ] = {}
    for start_char, end_char in sorted(proposed):
        interval = token_interval(start_char, end_char)
        if interval is None:
            continue
        start_token, end_token = interval
        normalized_interval = (token_rows[start_token][1], token_rows[end_token - 1][2])
        normalized_proposed.setdefault(normalized_interval, []).extend(
            proposed[(start_char, end_char)]
        )

    mention_rows: list[dict[str, Any]] = []
    license_rows: list[dict[str, Any]] = []
    for start_char, end_char in sorted(normalized_proposed):
        interval = token_interval(start_char, end_char)
        if interval is None:
            continue
        start_token, end_token = interval
        start_char = token_rows[start_token][1]
        end_char = token_rows[end_token - 1][2]
        mention_ref = f"mention:{document}:{start_char}:{end_char}"
        specifications = sorted(
            set(normalized_proposed[(start_char, end_char)]),
            key=lambda specification: legacy._LICENSE_PRIORITY[specification[0]],
        )
        primary_kind = specifications[0][0]
        mention_rows.append(
            legacy.MentionSpan(
                mention_ref=mention_ref,
                source_ref=source,
                document_ref=document,
                start_char=start_char,
                end_char=end_char,
                canonical_surface=text[start_char:end_char],
                generation_reason=primary_kind,
                grammatical_role=(
                    "eventuality_predicate"
                    if primary_kind == "eventuality_annotation"
                    else None
                ),
                context_refs=canonical_context_refs,
                start_token=start_token,
                end_token=end_token,
            ).to_dict()
        )
        for license_index, (license_kind, expected_kinds, local_types) in enumerate(
            specifications
        ):
            license_rows.append(
                legacy.MentionLicense(
                    license_ref=f"license:{mention_ref}:{license_kind}:{license_index}",
                    mention_ref=mention_ref,
                    license_kind=license_kind,
                    expected_candidate_kinds=expected_kinds,
                    local_type_hypotheses=local_types,
                    priority=legacy._LICENSE_PRIORITY[license_kind],
                ).to_dict()
            )

    mention_rows.sort(key=lambda mention: mention["mention_ref"])
    license_rows.sort(key=lambda license_row: license_row["license_ref"])
    suppressed_rows = sorted(
        (span.to_dict() for span in suppressed),
        key=lambda span: (
            span["start_token"],
            span["end_token"],
            span["suppression_reason"],
        ),
    )
    identity = {
        "schema_version": legacy.MENTION_LICENSING_SCHEMA_VERSION,
        "authority": legacy.ENTITY_RESOLUTION_AUTHORITY,
        "source_ref": source,
        "document_ref": document,
        "canonical_text_sha256": legacy._canonical_digest(text),
        "lattice": {
            "token_count": len(token_rows),
            "token_boundary_count": len(token_rows) + 1,
            "recoverable_contiguous_span_count": len(token_rows)
            * (len(token_rows) + 1)
            // 2,
        },
        "mentions": mention_rows,
        "licenses": license_rows,
        "suppressed_spans": suppressed_rows,
    }
    carrier = {
        **identity,
        "carrier_ref": f"mention-licensing:{legacy._canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "materialized_mention_count": len(mention_rows),
            "license_count": len(license_rows),
            "suppressed_span_count": len(suppressed_rows),
            "eventuality_license_count": sum(
                row["license_kind"] == "eventuality_annotation" for row in license_rows
            ),
        },
    }
    owner_merge_ended_ns = time_ns()
    execution_ended_ns = owner_merge_ended_ns
    fingerprint = canonical_sha256(_semantic_payload(carrier))
    serial_fingerprint: str | None = None
    parity: bool | None = None
    if verify_serial:
        serial = legacy.build_mention_licensing_carrier(
            canonical_text=text,
            source_ref=source,
            document_ref=document,
            context_refs=canonical_context_refs,
            parsed_document=parsed,
            tokens=token_rows,
        )
        serial_fingerprint = canonical_sha256(_semantic_payload(serial))
        parity = serial_fingerprint == fingerprint
        if not parity:
            raise ValueError("parallel mention licensing disagrees with serial carrier")

    peak_active_workers = _peak_active_workers(results)
    receipt = {
        "contract_ref": DOCUMENT_GRAPH_MENTION_CONTRACT,
        "execution_mode": "process_token_fibres",
        "requested_workers": requested_workers,
        "granted_workers": granted_workers,
        "peak_active_workers": peak_active_workers,
        "partition_count": len(partitions),
        "partitions": [
            {
                "sequence_no": int(result["sequence_no"]),
                "start_token": int(result["start_token"]),
                "end_token": int(result["end_token"]),
                "token_count": int(result["end_token"]) - int(result["start_token"]),
                "worker_pid": int(result["worker_pid"]),
                "started_ns": int(result["started_ns"]),
                "ended_ns": int(result["ended_ns"]),
                "compute_ms": int(result["compute_ms"]),
            }
            for result in sorted(results, key=lambda row: int(row["sequence_no"]))
        ],
        "worker_pids": sorted({int(result["worker_pid"]) for result in results}),
        "worker_compute_ms": sum(int(result["compute_ms"]) for result in results),
        "owner_merge_ms": max(
            0, (owner_merge_ended_ns - owner_merge_started_ns) // 1_000_000
        ),
        "wall_elapsed_ms": max(
            0, (execution_ended_ns - execution_started_ns) // 1_000_000
        ),
        "tokens_scanned": len(token_rows),
        "candidate_intervals": len(proposed),
        "mentions_licensed": len(mention_rows),
        "licenses_emitted": len(license_rows),
        "suppressed_spans": len(suppressed_rows),
        "semantic_fingerprint": fingerprint,
        "serial_fingerprint": serial_fingerprint,
        "serial_parallel_parity": parity,
        "budget_invariant_satisfied": peak_active_workers <= requested_workers,
        "semantic_object": "document",
        "fibre_semantic_authority": False,
        "authority": "execution_receipt_only",
    }
    if progress_observer is not None:
        progress_observer(
            {
                "tokens_scanned": len(token_rows),
                "mentions_considered": len(proposed),
                "mentions_licensed": len(mention_rows),
                "forms_derived": 0,
                "recurrences_derived": 0,
            }
        )
    return {**carrier, "licensing_execution_receipt": receipt}


__all__ = [
    "DOCUMENT_GRAPH_MENTION_CONTRACT",
    "build_document_mention_licensing_carrier",
]
