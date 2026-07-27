"""Document-scoped relational projection over immutable parser sentence fibres.

This module is the first executable cut of the document-graph dataflow model.  It
keeps one document-level semantic object while treating sentence partitions as
physical work units only.  Workers return additive relational deltas with global
coordinates; the caller performs one deterministic keyed merge.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import os
from time import time_ns
from typing import Any, Callable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.sensiblaw.interfaces.shared_reducer import (
    collect_canonical_relational_bundle,
)


DOCUMENT_GRAPH_PROJECTION_CONTRACT = "document-graph-relational-projection:v0_1"


@dataclass(frozen=True, slots=True)
class ProjectionPartition:
    sequence_no: int
    start_char: int
    end_char: int
    sentences: tuple[Mapping[str, Any], ...]
    token_count: int
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_no": self.sequence_no,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "sentence_count": len(self.sentences),
            "token_count": self.token_count,
            "word_count": self.word_count,
        }


def _sentence_start(sentence: Mapping[str, Any]) -> int:
    return int(sentence.get("start", sentence.get("start_char", 0)))


def _sentence_end(sentence: Mapping[str, Any]) -> int:
    start = _sentence_start(sentence)
    return int(sentence.get("end", sentence.get("end_char", start)))


def _sentence_word_count(sentence: Mapping[str, Any]) -> int:
    return len([part for part in str(sentence.get("text") or "").split() if part])


def _partition_sentences(
    sentences: Sequence[Mapping[str, Any]],
    *,
    worker_budget: int,
    partitions_per_worker: int,
) -> tuple[ProjectionPartition, ...]:
    """Build contiguous, cost-balanced physical partitions.

    Token count is used as the cheap cost signal.  More partitions than workers
    are deliberately produced to avoid tail latency from one unusually expensive
    sentence range.
    """

    rows = tuple(sentence for sentence in sentences if isinstance(sentence, Mapping))
    if not rows:
        return ()
    desired = min(
        len(rows),
        max(1, worker_budget * max(1, partitions_per_worker)),
    )
    total_tokens = sum(len(sentence.get("tokens") or ()) for sentence in rows)
    target_tokens = max(1, (total_tokens + desired - 1) // desired)

    groups: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    current_tokens = 0
    remaining_desired = desired
    for index, sentence in enumerate(rows):
        sentence_tokens = len(sentence.get("tokens") or ())
        remaining_sentences = len(rows) - index
        should_close = (
            current
            and current_tokens + sentence_tokens > target_tokens
            and remaining_sentences >= remaining_desired
        )
        if should_close:
            groups.append(current)
            current = []
            current_tokens = 0
            remaining_desired -= 1
        current.append(sentence)
        current_tokens += sentence_tokens
    if current:
        groups.append(current)

    partitions: list[ProjectionPartition] = []
    for sequence_no, group in enumerate(groups):
        partitions.append(
            ProjectionPartition(
                sequence_no=sequence_no,
                start_char=_sentence_start(group[0]),
                end_char=_sentence_end(group[-1]),
                sentences=tuple(group),
                token_count=sum(len(sentence.get("tokens") or ()) for sentence in group),
                word_count=sum(_sentence_word_count(sentence) for sentence in group),
            )
        )
    return tuple(partitions)


def _is_question_relation(relation: Mapping[str, Any]) -> bool:
    return str(relation.get("type") or "") == "composition" and any(
        str(role.get("role") or "") == "mode"
        and str(role.get("value") or "") == "question"
        for role in relation.get("roles") or ()
        if isinstance(role, Mapping)
    )


def _question_role(parsed_document: Mapping[str, Any]) -> dict[str, Any] | None:
    """Preserve the legacy document-global first-question projection."""

    for sentence in parsed_document.get("sents") or ():
        tokens = tuple(sentence.get("tokens") or ())
        question_mark = next(
            (token for token in tokens if str(token.get("text") or "") == "?"),
            None,
        )
        if question_mark is not None:
            return {
                "role": "mode",
                "value": "question",
                "span_start": int(question_mark["start"]),
                "span_end": int(question_mark["end"]),
            }
        token_by_index = {int(token["index"]): token for token in tokens}
        for token in tokens:
            if str(token.get("tag") or "") in {"WP", "WRB", "WDT"}:
                return {
                    "role": "mode",
                    "value": "question",
                    "span_start": int(token["start"]),
                    "span_end": int(token["end"]),
                }
            if str(token.get("dep") or "") != "aux":
                continue
            head = token_by_index.get(int(token.get("head_index", token["index"])))
            if (
                head is not None
                and str(head.get("pos") or "") in {"VERB", "AUX"}
                and int(token["index"]) < int(head["index"])
            ):
                return {
                    "role": "mode",
                    "value": "question",
                    "span_start": int(token["start"]),
                    "span_end": int(token["end"]),
                }
    return None


def _relation_key(relation: Mapping[str, Any]) -> tuple[Any, ...]:
    parts: list[Any] = [str(relation["type"])]
    for role in relation.get("roles") or ():
        value = role.get("value")
        if isinstance(value, Mapping):
            value = tuple(sorted((str(key), str(item)) for key, item in value.items()))
        parts.append((str(role["role"]), role.get("atom"), value))
    return tuple(parts)


def _numeric_local_id(value: str, prefix: str) -> tuple[int, str]:
    if value.startswith(prefix) and value[len(prefix) :].isdigit():
        return int(value[len(prefix) :]), value
    return 10**18, value


def _projection_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    started_ns = time_ns()
    text = str(payload["text"])
    parsed = {
        "text": text,
        "sents": tuple(payload["sentences"]),
    }
    bundle = collect_canonical_relational_bundle(text, parsed_document=parsed)
    ended_ns = time_ns()
    return {
        "sequence_no": int(payload["sequence_no"]),
        "partition": dict(payload["partition"]),
        "bundle": {
            **bundle,
            "relations": [
                relation
                for relation in bundle.get("relations") or ()
                if not _is_question_relation(relation)
            ],
        },
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


def _merge_partition_results(
    *,
    canonical_text: str,
    parsed_document: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    merge_started_ns = time_ns()
    atoms_by_key: dict[tuple[str, int, int], dict[str, Any]] = {}
    atom_id_by_key: dict[tuple[str, int, int], str] = {}
    relations: list[dict[str, Any]] = []
    relation_keys: set[tuple[Any, ...]] = set()

    def admit_atom(payload: Mapping[str, Any]) -> str:
        span = tuple(payload.get("span") or (0, 0))
        key = (str(payload.get("text") or ""), int(span[0]), int(span[1]))
        existing = atom_id_by_key.get(key)
        if existing is not None:
            return existing
        atom_id = f"a{len(atom_id_by_key) + 1}"
        atom_id_by_key[key] = atom_id
        atoms_by_key[key] = {**dict(payload), "id": atom_id}
        return atom_id

    def append_relation(type_: str, roles: list[dict[str, Any]]) -> None:
        candidate = {"type": type_, "roles": roles}
        key = _relation_key(candidate)
        if key in relation_keys:
            return
        relation_keys.add(key)
        relations.append(
            {
                "id": f"e{len(relations) + 1}",
                "type": type_,
                "roles": roles,
            }
        )

    for result in sorted(results, key=lambda row: int(row["sequence_no"])):
        bundle = result["bundle"]
        local_atoms = {
            str(atom["id"]): atom for atom in bundle.get("atoms") or ()
        }
        admitted_local_ids: set[str] = set()
        for relation in bundle.get("relations") or ():
            remapped_roles: list[dict[str, Any]] = []
            for role in relation.get("roles") or ():
                remapped = dict(role)
                local_atom_id = remapped.get("atom")
                if local_atom_id is not None:
                    local_atom_id = str(local_atom_id)
                    remapped["atom"] = admit_atom(local_atoms[local_atom_id])
                    admitted_local_ids.add(local_atom_id)
                remapped_roles.append(remapped)
            append_relation(str(relation["type"]), remapped_roles)
        for local_id in sorted(
            set(local_atoms) - admitted_local_ids,
            key=lambda value: _numeric_local_id(value, "a"),
        ):
            admit_atom(local_atoms[local_id])

    question_role = _question_role(parsed_document)
    if question_role is not None:
        append_relation("composition", [question_role])

    atoms = sorted(
        atoms_by_key.values(),
        key=lambda atom: (
            int(atom["span"][0]),
            int(atom["span"][1]),
            _numeric_local_id(str(atom["id"]), "a"),
        ),
    )
    merge_ended_ns = time_ns()
    return {
        "version": "relational_bundle_v1",
        "canonical_text": canonical_text,
        "atoms": atoms,
        "relations": relations,
        "merge_ms": max(0, (merge_ended_ns - merge_started_ns) // 1_000_000),
    }


def _semantic_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": bundle.get("version"),
        "canonical_text": bundle.get("canonical_text"),
        "atoms": list(bundle.get("atoms") or ()),
        "relations": list(bundle.get("relations") or ()),
    }


def collect_document_relational_bundle(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    parsed_document: Mapping[str, Any] | None = None,
    progress_callback: Callable[[str, Mapping[str, Any]], None] | None = None,
    worker_budget: int = 1,
    partitions_per_worker: int = 2,
    min_parallel_sentences: int = 4,
    verify_serial: bool = False,
) -> dict[str, Any]:
    """Project one parsed document using process-local sentence fibres.

    The semantic payload is deliberately identical to the serial reducer.  The
    additional receipt records physical execution only and has no semantic
    authority.
    """

    if parsed_document is None or worker_budget <= 1:
        serial = collect_canonical_relational_bundle(
            text,
            canonical_mode=canonical_mode,
            parsed_document=parsed_document,
            progress_callback=progress_callback,
        )
        fingerprint = canonical_sha256(_semantic_payload(serial))
        return {
            **serial,
            "projection_receipt": {
                "contract_ref": DOCUMENT_GRAPH_PROJECTION_CONTRACT,
                "execution_mode": "serial",
                "requested_workers": max(1, worker_budget),
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
    if str(parsed_document.get("text") or "") != text:
        raise ValueError("parsed_document text must equal text")

    sentences = tuple(parsed_document.get("sents") or ())
    if len(sentences) < max(2, min_parallel_sentences):
        return collect_document_relational_bundle(
            text,
            canonical_mode=canonical_mode,
            parsed_document=parsed_document,
            progress_callback=progress_callback,
            worker_budget=1,
            verify_serial=verify_serial,
        )

    partitions = _partition_sentences(
        sentences,
        worker_budget=worker_budget,
        partitions_per_worker=partitions_per_worker,
    )
    granted_workers = min(worker_budget, len(partitions))
    execution_started_ns = time_ns()
    results: list[dict[str, Any]] = []
    completed_sentences = 0
    completed_tokens = 0
    completed_words = 0
    total_tokens = sum(len(sentence.get("tokens") or ()) for sentence in sentences)
    total_words = sum(_sentence_word_count(sentence) for sentence in sentences)
    with ProcessPoolExecutor(
        max_workers=granted_workers,
    ) as executor:
        futures = {}
        for partition in partitions:
            fragment = text[partition.start_char : partition.end_char]
            payload = {
                "sequence_no": partition.sequence_no,
                "text": fragment,
                "sentences": partition.sentences,
                "partition": partition.to_dict(),
            }
            futures[executor.submit(_projection_worker, payload)] = partition
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            partition = futures[future]
            completed_sentences += len(partition.sentences)
            completed_tokens += partition.token_count
            completed_words += partition.word_count
            if progress_callback is not None:
                progress_callback(
                    "relational_bundle_progress",
                    {
                        "batch_index": len(results),
                        "total_batches": len(partitions),
                        "sentences_done": completed_sentences,
                        "total_sentences": len(sentences),
                        "words_done": completed_words,
                        "total_words": total_words,
                        "tokens_done": completed_tokens,
                        "total_tokens": total_tokens,
                        "atom_count": sum(
                            len(row["bundle"].get("atoms") or ()) for row in results
                        ),
                        "relation_count": sum(
                            len(row["bundle"].get("relations") or ()) for row in results
                        ),
                    },
                )

    merged = _merge_partition_results(
        canonical_text=text,
        parsed_document=parsed_document,
        results=results,
    )
    execution_ended_ns = time_ns()
    semantic_payload = _semantic_payload(merged)
    parallel_fingerprint = canonical_sha256(semantic_payload)
    serial_fingerprint: str | None = None
    parity: bool | None = None
    if verify_serial:
        serial = collect_canonical_relational_bundle(
            text,
            canonical_mode=canonical_mode,
            parsed_document=parsed_document,
        )
        serial_fingerprint = canonical_sha256(_semantic_payload(serial))
        parity = serial_fingerprint == parallel_fingerprint
        if not parity:
            raise ValueError("parallel relational projection disagrees with serial payload")

    peak_active_workers = _peak_active_workers(results)
    partition_receipts = [
        {
            **dict(result["partition"]),
            "worker_pid": int(result["worker_pid"]),
            "started_ns": int(result["started_ns"]),
            "ended_ns": int(result["ended_ns"]),
            "compute_ms": int(result["compute_ms"]),
        }
        for result in sorted(results, key=lambda row: int(row["sequence_no"]))
    ]
    receipt = {
        "contract_ref": DOCUMENT_GRAPH_PROJECTION_CONTRACT,
        "execution_mode": "process_sentence_fibres",
        "requested_workers": worker_budget,
        "granted_workers": granted_workers,
        "peak_active_workers": peak_active_workers,
        "partition_count": len(partitions),
        "partitions": partition_receipts,
        "worker_pids": sorted({int(result["worker_pid"]) for result in results}),
        "worker_compute_ms": sum(int(result["compute_ms"]) for result in results),
        "owner_merge_ms": int(merged.pop("merge_ms")),
        "wall_elapsed_ms": max(
            0, (execution_ended_ns - execution_started_ns) // 1_000_000
        ),
        "sentences_projected": len(sentences),
        "tokens_projected": total_tokens,
        "words_projected": total_words,
        "atoms_projected": len(semantic_payload["atoms"]),
        "relations_projected": len(semantic_payload["relations"]),
        "semantic_fingerprint": parallel_fingerprint,
        "serial_fingerprint": serial_fingerprint,
        "serial_parallel_parity": parity,
        "budget_invariant_satisfied": peak_active_workers <= worker_budget,
        "semantic_object": "document",
        "fibre_semantic_authority": False,
        "authority": "execution_receipt_only",
    }
    return {**merged, "projection_receipt": receipt}


__all__ = [
    "DOCUMENT_GRAPH_PROJECTION_CONTRACT",
    "ProjectionPartition",
    "collect_document_relational_bundle",
]
