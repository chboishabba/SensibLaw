"""Single-pass manifest annotation persistence for the in-process reader."""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.artifact_projection import iter_verified_records
from src.storage.postgres.manifest_metadata_hot_path import execution_scalar_metadata
from src.storage.postgres.work_conserving_language_persistence import (
    _persist_annotation_payloads,
)
from src.storage.postgres.work_conserving_stage import StagePayload, _sha


def persist_annotation_layer_batches_single_pass(
    self: Any,
    cursor: Any,
    *,
    document_ref: str,
    descriptor: Mapping[str, Any],
    reader: Any,
) -> None:
    """Persist one annotation manifest with at most one full record-stream pass."""

    del self
    metadata = execution_scalar_metadata(reader, descriptor)
    if metadata is None or not {"layer_ref", "text_sha256"}.issubset(metadata):
        # Reader implementations without the in-process immutable source retain
        # the established bounded preflight contract.
        metadata = {}
        for batch in reader.iter_records(str(descriptor["artifact_key"])):
            for record in batch:
                if record.get("reconstruction") == "mapping_scalar":
                    metadata[str(record["field"])] = record.get("value")

    layer_ref = str(metadata["layer_ref"])
    payloads: list[StagePayload] = []
    for batch in iter_verified_records(reader, descriptor):
        for record in batch:
            family = str(record.get("family") or "")
            row = record.get("value")
            if not isinstance(row, Mapping):
                continue
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


__all__ = ["persist_annotation_layer_batches_single_pass"]
