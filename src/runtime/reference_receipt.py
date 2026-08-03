"""Reference-backed receipt serialization without document-sized copies."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping

from src.pnf.streaming_build_reader import family_descriptor
from src.runtime.execution_resource_ledger import sample_process_resources


REFERENCE_RECEIPT_SCHEMA_VERSION = "sensiblaw.reference-receipt.v1"
SERIALIZER_REPORT_SCHEMA_VERSION = "sensiblaw.reference-serializer-report.v1"


def atomic_stream_json(path: str | Path, payload: Mapping[str, Any]) -> int:
    """Write one JSON mapping without first creating its complete encoded string."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    written = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for chunk in encoder.iterencode(dict(payload)):
            handle.write(chunk)
            written += len(chunk.encode("utf-8"))
        handle.write("\n")
        written += 1
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    return written


def stream_jsonl_family(
    path: str | Path,
    *,
    family: str,
    rows: Iterable[Mapping[str, Any]],
    manifest_ref: str | None = None,
) -> dict[str, Any]:
    """Write canonical rows incrementally and return a verified descriptor."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    digest = sha256()
    count = 0
    byte_count = 0
    with temporary.open("wb") as handle:
        for row in rows:
            encoded = (
                json.dumps(
                    dict(row),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            handle.write(encoded)
            digest.update(encoded)
            byte_count += len(encoded)
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    return family_descriptor(
        family=family,
        storage_kind="jsonl",
        record_count=count,
        byte_count=byte_count,
        ordered_digest=digest.hexdigest(),
        path=str(target),
        manifest_ref=manifest_ref,
    )


def serialize_reference_receipt(
    *,
    spec_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    """Serialize a compact spec in a fresh process and report its own peak view."""

    before = sample_process_resources()
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if not isinstance(spec, Mapping):
        raise ValueError("reference receipt spec must be a mapping")
    payload = {
        "schema_version": REFERENCE_RECEIPT_SCHEMA_VERSION,
        **dict(spec),
    }
    bytes_written = atomic_stream_json(output_path, payload)
    after = sample_process_resources()
    report = {
        "schema_version": SERIALIZER_REPORT_SCHEMA_VERSION,
        "state": "completed",
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
    }
    atomic_stream_json(report_path, report)
    return report


def run_isolated_reference_serializer(
    *,
    spec_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    hard_pss_bytes: int,
    python_executable: str | None = None,
) -> dict[str, Any]:
    """Launch a clean serializer process receiving paths and refs only."""

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
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if not isinstance(report, Mapping):
        raise ValueError("serializer report must be a mapping")
    observed = max(
        int((report.get("before") or {}).get("pss_bytes") or 0),
        int((report.get("after") or {}).get("pss_bytes") or 0),
    )
    if observed >= hard_pss_bytes:
        raise MemoryError(
            f"isolated serializer PSS {observed} exceeded {hard_pss_bytes}"
        )
    return dict(report)


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
    "REFERENCE_RECEIPT_SCHEMA_VERSION",
    "SERIALIZER_REPORT_SCHEMA_VERSION",
    "atomic_stream_json",
    "run_isolated_reference_serializer",
    "serialize_reference_receipt",
    "stream_jsonl_family",
]
