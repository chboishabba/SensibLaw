from __future__ import annotations

import json

import pytest

from src.storage.postgres.work_conserving_language_persistence import (
    _canonical_token_tuple_bytes,
)


@pytest.mark.parametrize(
    "token",
    (
        ("hello", 0, 5),
        ('a"b\\c\n\x00', -1, 7),
        ("café 🐕", 3, 9),
        ("\b\f\r\t", 1, 2),
    ),
)
def test_typed_token_identity_matches_established_bytes(
    token: tuple[str, int, int],
) -> None:
    expected = json.dumps(
        token,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    assert _canonical_token_tuple_bytes(token) == expected
