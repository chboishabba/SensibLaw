"""Direct bounded family reads for same-process sealed manifest artifacts.

The canonical manifest representation wraps each source value in a record envelope
(`family`, `ordinal`, `field`, `index`, `value`, `reconstruction`).  That envelope
is required for durable/reloaded readers and for digest verification.  When the
same in-process immutable source carries the exact producer descriptor seal,
PostgreSQL persistence can consume the requested family directly and avoid
allocating an envelope dict for every row.
"""

from __future__ import annotations

from itertools import islice
from typing import Any, Iterator, Mapping, Sequence

from src.policy.carrier_orchestration_hot_path import (
    _descriptor_matches_seal,
    _manifest_telemetry_stride,
)


def _mapping_rows(value: object) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for row in value:
            if isinstance(row, Mapping):
                yield row


def direct_sealed_descriptor_family(
    reader: Any,
    descriptor: Mapping[str, Any],
    family: str,
    *,
    batch_size: int = 256,
) -> Iterator[tuple[Mapping[str, Any], ...]] | None:
    """Return a direct family iterator, or ``None`` when full replay is required."""

    if batch_size < 1 or batch_size > 256:
        raise ValueError("record batch size must be between 1 and 256")
    if not _descriptor_matches_seal(reader, descriptor):
        return None
    sources = getattr(reader, "_sources", None)
    if not isinstance(sources, Mapping):
        return None
    artifact_key = str(descriptor.get("artifact_key") or "")
    source = sources.get(artifact_key)

    if isinstance(source, Mapping):
        if family not in source:
            rows: Iterator[Mapping[str, Any]] = iter(())
        else:
            rows = _mapping_rows(source[family])
    elif (
        family == "rows"
        and isinstance(source, Sequence)
        and not isinstance(source, (str, bytes, bytearray))
    ):
        rows = _mapping_rows(source)
    else:
        return None

    def batches() -> Iterator[tuple[Mapping[str, Any], ...]]:
        ledger = getattr(reader, "_resource_ledger", None)
        stride = _manifest_telemetry_stride()
        pending_rows = 0
        batch_no = 0
        while batch := tuple(islice(rows, batch_size)):
            batch_no += 1
            pending_rows += len(batch)
            if ledger is not None and batch_no % stride == 0:
                ledger.batch(
                    f"manifest_direct:{artifact_key}:{family}",
                    rows=pending_rows,
                    payload_bytes=0,
                )
                pending_rows = 0
            yield batch
        if ledger is not None and pending_rows:
            ledger.batch(
                f"manifest_direct:{artifact_key}:{family}",
                rows=pending_rows,
                payload_bytes=0,
            )

    return batches()


__all__ = ["direct_sealed_descriptor_family"]
