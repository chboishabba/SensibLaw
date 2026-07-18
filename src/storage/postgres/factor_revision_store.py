"""Persistence helper for one immutable factor revision."""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256


def factor_revision_ref(factor: Mapping[str, Any]) -> str:
    return f"factor-revision:{canonical_sha256(factor)}"


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def persist_factor_revision(
    cursor: Any,
    *,
    document_ref: str,
    factor: Mapping[str, Any],
) -> str:
    factor_ref = str(factor["factor_ref"])
    revision_ref = factor_revision_ref(factor)
    cursor.execute(
        """
        INSERT INTO algebra.factor (factor_ref, document_ref, factor_type_ref)
        VALUES (%s, %s, %s)
        ON CONFLICT (factor_ref) DO NOTHING
        """,
        (factor_ref, document_ref, str(factor["factor_type"])),
    )
    cursor.execute(
        """
        INSERT INTO algebra.factor_revision
            (factor_revision_ref, factor_ref, closure_state_ref, factor_sha256)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (factor_revision_ref) DO NOTHING
        """,
        (revision_ref, factor_ref, str(factor["closure_state"]), _sha(factor)),
    )
    for alternative in factor.get("alternatives") or ():
        alternative_ref = str(alternative["alternative_ref"])
        value = alternative.get("value")
        cursor.execute(
            """
            INSERT INTO algebra.alternative
                (alternative_ref, type_ref, value_ref, value_literal,
                 authority_state_ref, alternative_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (alternative_ref) DO NOTHING
            """,
            (
                alternative_ref,
                str(alternative["type_ref"]),
                str(value.get("mention_ref"))
                if isinstance(value, Mapping) and value.get("mention_ref")
                else None,
                None if isinstance(value, Mapping) else str(value),
                str(alternative.get("authority_state") or "candidate_only"),
                _sha(alternative),
            ),
        )
        cursor.execute(
            """
            INSERT INTO algebra.factor_revision_alternative
                (factor_revision_ref, alternative_ref, alternative_state_ref)
            VALUES (%s, %s, 'alternative') ON CONFLICT DO NOTHING
            """,
            (revision_ref, alternative_ref),
        )
    for residual in factor.get("residuals") or ():
        residual_ref = f"{revision_ref}:residual:{residual}"
        cursor.execute(
            """
            INSERT INTO algebra.residual
                (residual_ref, target_ref, residual_type_ref,
                 residual_state_ref, residual_sha256)
            VALUES (%s, %s, %s, 'open', %s)
            ON CONFLICT (residual_ref) DO NOTHING
            """,
            (
                residual_ref,
                revision_ref,
                str(residual),
                _sha({"factor_revision_ref": revision_ref, "residual": residual}),
            ),
        )
    return revision_ref


__all__ = ["factor_revision_ref", "persist_factor_revision"]
