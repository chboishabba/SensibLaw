from __future__ import annotations

import pytest

from src.pnf.streaming_build_reader import StreamingBuildReader
from src.runtime.reference_receipt import stream_jsonl_family


def test_reader_streams_and_verifies_jsonl_family(tmp_path) -> None:
    path = tmp_path / "factors.jsonl"
    descriptor = stream_jsonl_family(
        path,
        family="factors",
        rows=({"factor_ref": f"factor:{index}"} for index in range(5)),
    )
    build = {
        "family_manifests": {"factors": descriptor},
        "materialized_reduction": {"factors": descriptor},
    }
    reader = StreamingBuildReader(build)

    batches = tuple(reader.iter_batches("factors", batch_size=2))

    assert [len(batch) for batch in batches] == [2, 2, 1]
    assert reader.family_count("factors") == 5
    assert batches[-1][0]["factor_ref"] == "factor:4"


def test_reader_rejects_tampered_family(tmp_path) -> None:
    path = tmp_path / "proposals.jsonl"
    descriptor = stream_jsonl_family(
        path,
        family="proposals",
        rows=({"proposal_ref": "proposal:1"},),
    )
    path.write_text('{"proposal_ref":"proposal:2"}\n', encoding="utf-8")
    reader = StreamingBuildReader(
        {"family_manifests": {"proposals": descriptor}}
    )

    with pytest.raises(ValueError, match="digest|byte count"):
        tuple(reader.iter_rows("proposals"))
