from __future__ import annotations

from src.reporting.source_identity import (
    build_google_public_source_id,
    build_hashed_source_id,
    build_openrecall_capture_id,
    build_worldmonitor_capture_id,
    format_local_iso_and_date_from_timestamp,
    format_utc_iso_from_timestamp_ms,
)


def test_build_hashed_source_id_is_stable() -> None:
    assert build_hashed_source_id(prefix="messenger_export", raw="thread-a") == build_hashed_source_id(
        prefix="messenger_export",
        raw="thread-a",
    )


def test_google_public_source_id_formats_kind_specific_prefix() -> None:
    assert build_google_public_source_id(kind="doc", doc_id="abc123") == "google_doc:abc123"
    assert build_google_public_source_id(kind="sheet", doc_id="xyz789") == "google_sheet:xyz789"


def test_format_utc_iso_from_timestamp_ms_normalizes_to_z_suffix() -> None:
    assert format_utc_iso_from_timestamp_ms(1742526000000) == "2025-03-21T03:00:00Z"


def test_format_local_iso_and_date_from_timestamp_returns_pair() -> None:
    iso_value, date_value = format_local_iso_and_date_from_timestamp(1742526000)

    assert "T" in iso_value
    assert len(date_value) == 10


def test_build_openrecall_capture_id_is_stable() -> None:
    assert build_openrecall_capture_id(source_db_path="/tmp/recall.db", source_timestamp=1234) == build_openrecall_capture_id(
        source_db_path="/tmp/recall.db",
        source_timestamp=1234,
    )


def test_build_worldmonitor_capture_id_is_stable() -> None:
    assert build_worldmonitor_capture_id(source_path="/tmp/worldmonitor/gamma-irradiators.json", source_row_id="row-01") == build_worldmonitor_capture_id(
        source_path="/tmp/worldmonitor/gamma-irradiators.json",
        source_row_id="row-01",
    )
