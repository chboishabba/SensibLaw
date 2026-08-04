from __future__ import annotations

import json

from src.runtime.reference_receipt import (
    atomic_stream_json,
    run_isolated_reference_serializer,
    stream_jsonl_family,
)


def test_stream_jsonl_family_accepts_one_pass_generator(tmp_path) -> None:
    consumed: list[int] = []

    def rows():
        for index in range(4):
            consumed.append(index)
            yield {"index": index}

    descriptor = stream_jsonl_family(
        tmp_path / "rows.jsonl",
        family="rows",
        rows=rows(),
    )

    assert consumed == [0, 1, 2, 3]
    assert descriptor["record_count"] == 4
    assert descriptor["byte_count"] == (tmp_path / "rows.jsonl").stat().st_size


def test_isolated_serializer_receives_only_compact_spec(tmp_path) -> None:
    spec = tmp_path / "spec.json"
    output = tmp_path / "receipt.json"
    report = tmp_path / "report.json"
    atomic_stream_json(
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

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["document_ref"] == "document:test"
    assert result["received_owner_object"] is False
    assert result["reference_only"] is True
