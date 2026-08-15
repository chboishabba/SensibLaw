"""Single-pass/direct manifest annotation persistence for the in-process reader."""

from __future__ import annotations

from contextlib import contextmanager
from types import MethodType
from typing import Any, Iterator, Mapping, Sequence

from src.policy.artifact_projection import iter_verified_records
from src.policy.carrier_orchestration_hot_path import _descriptor_matches_seal
from src.storage.postgres.manifest_metadata_hot_path import execution_scalar_metadata
from src.storage.postgres.work_conserving_language_persistence import (
    _persist_annotation_payloads,
)
from src.storage.postgres.work_conserving_stage import StagePayload, _sha


def _append_annotation_rows(
    payloads: list[StagePayload],
    *,
    layer_ref: str,
    family: str,
    rows: Sequence[object],
) -> int:
    admitted = 0
    for value in rows:
        if not isinstance(value, Mapping):
            continue
        row = value
        if family == "token_annotations":
            payloads.append(
                StagePayload(
                    "annotation_node",
                    texts=(
                        f"{layer_ref}:token:{row['token_index']}",
                        layer_ref,
                        str(row["annotation_type"]),
                        None,
                        str(row["value"]),
                    ),
                )
            )
        elif family == "span_annotations":
            payloads.append(
                StagePayload(
                    "annotation_node",
                    texts=(
                        str(row["span_ref"]),
                        layer_ref,
                        str(row["annotation_type"]),
                        str(row["span_ref"]),
                        str((row.get("value") or {}).get("surface") or ""),
                    ),
                )
            )
        elif family == "relation_annotations":
            payloads.append(
                StagePayload(
                    "annotation_relation",
                    texts=(
                        str(row["relation_ref"]),
                        layer_ref,
                        str(row["relation_type"]),
                        str(row["left_ref"]),
                        str(row["right_ref"]),
                    ),
                )
            )
        else:
            continue
        admitted += 1
    return admitted


def _direct_annotation_source(reader: Any, descriptor: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if not _descriptor_matches_seal(reader, descriptor):
        return None
    sources = getattr(reader, "_sources", None)
    if not isinstance(sources, Mapping):
        return None
    source = sources.get(str(descriptor.get("artifact_key") or ""))
    return source if isinstance(source, Mapping) else None


def persist_annotation_layer_batches_single_pass(
    self: Any,
    cursor: Any,
    *,
    document_ref: str,
    descriptor: Mapping[str, Any],
    reader: Any,
) -> None:
    """Persist one annotation manifest with no duplicate envelope traversal."""

    del self
    metadata = execution_scalar_metadata(reader, descriptor)
    if metadata is None or not {"layer_ref", "text_sha256"}.issubset(metadata):
        metadata = {}
        for batch in reader.iter_records(str(descriptor["artifact_key"])):
            for record in batch:
                if record.get("reconstruction") == "mapping_scalar":
                    metadata[str(record["field"])] = record.get("value")

    layer_ref = str(metadata["layer_ref"])
    payloads: list[StagePayload] = []
    source = _direct_annotation_source(reader, descriptor)
    if source is not None and execution_scalar_metadata(reader, descriptor) is not None:
        direct_rows = 0
        for family in (
            "token_annotations",
            "span_annotations",
            "relation_annotations",
        ):
            rows = source.get(family) or ()
            if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray)):
                direct_rows += _append_annotation_rows(
                    payloads,
                    layer_ref=layer_ref,
                    family=family,
                    rows=rows,
                )
        ledger = getattr(reader, "_resource_ledger", None)
        if ledger is not None and direct_rows:
            ledger.batch(
                f"manifest_direct:{descriptor['artifact_key']}:annotations",
                rows=direct_rows,
                payload_bytes=0,
            )
    else:
        for batch in iter_verified_records(reader, descriptor):
            for record in batch:
                family = str(record.get("family") or "")
                row = record.get("value")
                if isinstance(row, Mapping):
                    _append_annotation_rows(
                        payloads,
                        layer_ref=layer_ref,
                        family=family,
                        rows=(row,),
                    )

    _persist_annotation_payloads(
        cursor,
        document_ref=document_ref,
        layer_ref=layer_ref,
        backend_ref=str(metadata.get("tokenizer_ref") or "unknown"),
        input_sha256=bytes.fromhex(str(metadata["text_sha256"])),
        output_sha256=_sha(metadata),
        payloads=payloads,
        family_ref="annotation_layer_manifest",
    )


@contextmanager
def activate_annotation_metadata_hot_path(store: Any) -> Iterator[None]:
    """Install the optimized annotation method after the base store binding."""

    prior = store.persist_annotation_layer_batches
    store.persist_annotation_layer_batches = MethodType(
        persist_annotation_layer_batches_single_pass,
        store,
    )
    try:
        yield
    finally:
        store.persist_annotation_layer_batches = prior


__all__ = [
    "activate_annotation_metadata_hot_path",
    "persist_annotation_layer_batches_single_pass",
]
