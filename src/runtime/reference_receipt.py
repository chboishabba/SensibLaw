"""Reference-backed receipt persistence without text serialization.

Specs, compact receipts, reports, and family rows use framed protocol-5 binary
artifacts. Semantic identity is computed from typed canonical bytes, while raw
artifact bytes receive an independent SHA-256 so readers can verify them before
decode. The artifact codec is only a bounded local handoff between processes.
"""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import pickle
import subprocess
import sys
from typing import Any, Iterable, Mapping

from src.pnf.streaming_build_reader import (
    BINARY_FAMILY_ENCODING,
    family_descriptor,
)
from src.policy.carriers.canonical import canonical_bytes
from src.runtime.execution_resource_ledger import sample_process_resources


REFERENCE_RECEIPT_SCHEMA_VERSION = "sensiblaw.reference-receipt.v3"
SERIALIZER_REPORT_SCHEMA_VERSION = "sensiblaw.reference-serializer-report.v3"
BINARY_RECEIPT_ENCODING = "python-pickle:5+sha256+itir-typed-digest:v1"


def atomic_write_binary(path: str | Path, payload: Mapping[str, Any]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    encoded = pickle.dumps(dict(payload), protocol=5)
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    return len(encoded)


def stream_binary_family(
    path: str | Path,
    *,
    family: str,
    rows: Iterable[Mapping[str, Any]],
    manifest_ref: str | None = None,
) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    semantic_digest = sha256()
    artifact_digest = sha256()
    count = 0
    semantic_byte_count = 0
    artifact_byte_count = 0
    with temporary.open("wb") as handle:
        for row in rows:
            value = dict(row)
            encoded = pickle.dumps(value, protocol=5)
            frame = len(encoded).to_bytes(8, "big") + encoded
            handle.write(frame)
            artifact_digest.update(frame)
            artifact_byte_count += len(frame)

            semantic = canonical_bytes(value)
            semantic_frame = len(semantic).to_bytes(8, "big") + semantic
            semantic_digest.update(semantic_frame)
            semantic_byte_count += len(semantic_frame)
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    return family_descriptor(
        family=family,
        storage_kind="binary",
        record_count=count,
        byte_count=semantic_byte_count,
        artifact_byte_count=artifact_byte_count,
        artifact_digest=artifact_digest.hexdigest(),
        ordered_digest=semantic_digest.hexdigest(),
        path=str(target),
        manifest_ref=manifest_ref,
        encoding_ref=BINARY_FAMILY_ENCODING,
    )


def _load_binary_mapping(path: str | Path) -> dict[str, Any]:
    value = pickle.loads(Path(path).read_bytes())
    if not isinstance(value, Mapping):
        raise ValueError(f"binary receipt artifact is not a mapping: {path}")
    return dict(value)


def serialize_reference_receipt(
    *,
    spec_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    before = sample_process_resources()
    spec = _load_binary_mapping(spec_path)
    payload = {
        "schema_version": REFERENCE_RECEIPT_SCHEMA_VERSION,
        "encoding_ref": BINARY_RECEIPT_ENCODING,
        **spec,
    }
    bytes_written = atomic_write_binary(output_path, payload)
    after = sample_process_resources()
    report = {
        "schema_version": SERIALIZER_REPORT_SCHEMA_VERSION,
        "state": "completed",
        "encoding_ref": BINARY_RECEIPT_ENCODING,
        "spec_path": str(Path(spec_path)),
        "output_path": str(Path(output_path)),
        "bytes_written": bytes_written,
        "before": dict(before),
        "after": dict(after),
        "pss_growth_bytes": max(
            0, int(after["pss_bytes"]) - int(before["pss_bytes"])
        ),
        "received_owner_object": False,
        "reference_only": True,
        "text_serialization": False,
    }
    atomic_write_binary(report_path, report)
    return report


def run_isolated_reference_serializer(
    *,
    spec_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    hard_pss_bytes: int,
    python_executable: str | None = None,
) -> dict[str, Any]:
    command = [
        python_executable or sys.executable,
        "-m",
        "src.runtime.reference_receipt",
        "--spec",
        str(spec_path),
        "--output",
        str(output_path),
        "--report",
        str(report_path),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"reference receipt serializer failed with {completed.returncode}"
        )
    report = _load_binary_mapping(report_path)
    observed = max(
        int((report.get("before") or {}).get("pss_bytes") or 0),
        int((report.get("after") or {}).get("pss_bytes") or 0),
    )
    if observed >= hard_pss_bytes:
        raise MemoryError(
            f"isolated serializer PSS {observed} exceeded {hard_pss_bytes}"
        )
    return report


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    serialize_reference_receipt(
        spec_path=args.spec,
        output_path=args.output,
        report_path=args.report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "BINARY_RECEIPT_ENCODING",
    "REFERENCE_RECEIPT_SCHEMA_VERSION",
    "SERIALIZER_REPORT_SCHEMA_VERSION",
    "atomic_write_binary",
    "run_isolated_reference_serializer",
    "serialize_reference_receipt",
    "stream_binary_family",
]
