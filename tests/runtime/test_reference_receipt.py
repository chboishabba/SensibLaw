from __future__ import annotations

import pickle

from src.runtime.reference_receipt import (
    atomic_write_binary,
    run_isolated_reference_serializer,
    stream_binary_family,
)


def test_stream_binary_family_accepts_one_pass_generator(tmp_path) -> None:
    consumed: list[int] = []

    def rows():
        for index in range(4):
            consumed.append(index)
            yield {"index": index}

    path = tmp_path / "rows.bin"
    descriptor = stream_binary_family(
        path,
        family="rows",
        rows=rows(),
    )

    assert consumed == [0, 1, 2, 3]
    assert descriptor["record_count"] == 4
    assert descriptor["artifact_byte_count"] == path.stat().st_size
    assert descriptor["storage_kind"] == "binary"


def test_isolated_serializer_receives_only_compact_binary_spec(tmp_path) -> None:
    spec = tmp_path / "spec.pkl"
    output = tmp_path / "receipt.pkl"
    report = tmp_path / "report.pkl"
    atomic_write_binary(
        spec,
        {
            "document_ref": "document:test",
            "family_manifests": {
                "factors": {
                    "record_count": 100,
                    "ordered_digest": "abc",
                }
            },
        },
    )

    result = run_isolated_reference_serializer(
        spec_path=spec,
        output_path=output,
        report_path=report,
        hard_pss_bytes=512 * 1024 * 1024,
    )

    receipt = pickle.loads(output.read_bytes())
    assert receipt["document_ref"] == "document:test"
    assert receipt["encoding_ref"].startswith("python-pickle:5")
    assert result["received_owner_object"] is False
    assert result["reference_only"] is True
    assert result["text_serialization"] is False
