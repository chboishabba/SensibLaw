from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any


def build_hashed_source_id(*, prefix: str, raw: str, digest_len: int = 12) -> str:
    normalized = str(raw or "").strip()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[: int(digest_len)]
    return f"{prefix}:{digest}"


def build_google_public_source_id(*, kind: str, doc_id: str) -> str:
    normalized_kind = str(kind or "").strip().lower()
    normalized_doc_id = str(doc_id or "").strip()
    if normalized_kind == "doc":
        return f"google_doc:{normalized_doc_id}"
    if normalized_kind == "sheet":
        return f"google_sheet:{normalized_doc_id}"
    raise ValueError(f"unsupported google public kind: {kind}")


def format_utc_iso_from_timestamp_ms(timestamp_ms: Any) -> str:
    value = int(timestamp_ms)
    return (
        datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def format_local_iso_and_date_from_timestamp(timestamp_s: int) -> tuple[str, str]:
    local_dt = datetime.fromtimestamp(int(timestamp_s)).astimezone()
    return local_dt.isoformat(timespec="seconds"), local_dt.date().isoformat()


def build_openrecall_capture_id(*, source_db_path: str, source_timestamp: int) -> str:
    return build_hashed_source_id(
        prefix="openrecall",
        raw=f"{source_db_path}|{int(source_timestamp)}",
        digest_len=16,
    )


def build_worldmonitor_capture_id(*, source_path: str, source_row_id: str) -> str:
    return build_hashed_source_id(
        prefix="worldmonitor",
        raw=f"{source_path}|{source_row_id}",
        digest_len=16,
    )


__all__ = [
    "build_google_public_source_id",
    "build_hashed_source_id",
    "build_openrecall_capture_id",
    "build_worldmonitor_capture_id",
    "format_local_iso_and_date_from_timestamp",
    "format_utc_iso_from_timestamp_ms",
]
