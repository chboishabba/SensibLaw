"""Generic external snapshot and assertion persistence.

Registry-specific adapters normalize into this envelope before persistence.
The store does not select identity or coerce observations into occurrences.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def persist_external_snapshot(
    cursor: Any,
    *,
    snapshot_ref: str,
    registry_ref: str,
    external_ref: str,
    revision_ref: str,
    formal_type_ref: str | None,
    payload_sha256: str,
    raw_content_ref: str | None = None,
    fetched_at: Any | None = None,
    assertions: Sequence[Mapping[str, Any]] = (),
) -> None:
    cursor.execute(
        """
        INSERT INTO evidence.snapshot
            (snapshot_ref, registry_ref, external_ref, revision_ref,
             formal_type_ref, payload_sha256, raw_content_ref, fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_ref) DO NOTHING
        """,
        (
            snapshot_ref,
            registry_ref,
            external_ref,
            revision_ref,
            formal_type_ref,
            bytes.fromhex(payload_sha256),
            raw_content_ref,
            fetched_at,
        ),
    )
    for assertion in assertions:
        object_ref = assertion.get("object_ref")
        object_literal = assertion.get("object_literal")
        if (object_ref is None) == (object_literal is None):
            raise ValueError("snapshot assertions require exactly one object form")
        identity = {
            "snapshot_ref": snapshot_ref,
            "subject_ref": assertion["subject_ref"],
            "predicate_ref": assertion["predicate_ref"],
            "object_ref": object_ref,
            "object_literal": object_literal,
            "assertion_role_ref": assertion["assertion_role_ref"],
        }
        assertion_ref = str(
            assertion.get("assertion_ref")
            or "assertion:" + canonical_sha256(identity)
        )
        cursor.execute(
            """
            INSERT INTO evidence.assertion
                (assertion_ref, snapshot_ref, subject_ref, predicate_ref,
                 object_ref, object_literal, assertion_role_ref,
                 assertion_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (assertion_ref) DO NOTHING
            """,
            (
                assertion_ref,
                snapshot_ref,
                str(assertion["subject_ref"]),
                str(assertion["predicate_ref"]),
                str(object_ref) if object_ref is not None else None,
                str(object_literal) if object_literal is not None else None,
                str(assertion["assertion_role_ref"]),
                _sha(identity),
            ),
        )


__all__ = ["persist_external_snapshot"]
