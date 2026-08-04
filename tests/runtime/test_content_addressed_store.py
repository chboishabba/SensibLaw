from __future__ import annotations

from io import BytesIO

from src.runtime.content_addressed_store import (
    FilesystemContentAddressedStore,
    register_payload_segment,
)


class RecordingCursor:
    def __init__(self) -> None:
        self.query = ""
        self.parameters = None

    def execute(self, query, parameters=None) -> None:
        self.query = query
        self.parameters = parameters


def test_filesystem_store_deduplicates_and_verifies(tmp_path) -> None:
    store = FilesystemContentAddressedStore(tmp_path / "objects")

    first = store.put_stream(
        BytesIO(b"large semantic payload"),
        media_type="application/x-ndjson",
    )
    second = store.put_stream(
        BytesIO(b"large semantic payload"),
        media_type="application/x-ndjson",
    )

    assert first.payload_ref == second.payload_ref
    assert first.locator == second.locator
    assert first.byte_count == len(b"large semantic payload")
    assert store.verify(first) is True
    with store.open_payload(first) as stream:
        assert stream.read() == b"large semantic payload"


def test_segment_registration_keeps_postgres_authoritative(tmp_path) -> None:
    store = FilesystemContentAddressedStore(tmp_path / "objects")
    payload = store.put_stream(
        BytesIO(b'{"factor_ref":"factor:1"}\n'),
        media_type="application/x-ndjson",
    )
    cursor = RecordingCursor()

    register_payload_segment(
        cursor,
        segment_ref="segment:1",
        manifest_ref="manifest:1",
        family_ref="factors",
        sequence_start=0,
        sequence_end=1,
        record_count=1,
        payload=payload,
        encoding_ref="canonical-jsonl:v1",
    )

    assert "execution.semantic_graph_family_segment" in cursor.query
    assert cursor.parameters[0] == "segment:1"
    assert cursor.parameters[8] == "filesystem-content-addressed"
    assert cursor.parameters[9] == payload.locator
