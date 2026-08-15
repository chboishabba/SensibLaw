from __future__ import annotations

from src.policy import artifact_projection
from src.policy import carrier_orchestration_hot_path as hot


def test_reused_encoder_digest_matches_established_manifest_digest() -> None:
    records = (
        {
            "family": "rows",
            "ordinal": 0,
            "value": {
                "unicode": "Finland – 日本",
                "quotes": 'a"b\\c',
                "bools": [True, False, None],
                "ints": [-1, 0, 2**53],
                "floats": [-0.0, 1.25, 1e-09, 1e20],
                "nested": {"z": 1, "a": [3, 2, 1]},
            },
            "reconstruction": "sequence_member",
        },
        {
            "family": "rows",
            "ordinal": 1,
            "value": {"control": "line\nfeed\ttab", "empty": {}},
            "reconstruction": "sequence_member",
        },
    )

    established = artifact_projection._record_stream_digest(iter(records))
    optimized = hot._reused_encoder_record_stream_digest(iter(records))

    assert optimized == established


def test_reused_encoder_record_bytes_match_established_json_options() -> None:
    record = {
        "z": "é",
        "a": {"β": 2, "alpha": 1},
        "n": None,
        "f": 1.2345678901234567,
    }
    expected = artifact_projection.json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert hot._canonical_record_bytes(record) == expected
