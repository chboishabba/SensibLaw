"""Reusable document-level build receipts for the operational compiler."""

from __future__ import annotations

from typing import Any, Sequence

from src.policy.carriers.canonical import canonical_sha256


_OPERATION_REF = "compiler.document.local-binding"
_OPERATION_VERSION = "v0_8"


def _digest(value: str) -> bytes:
    return bytes.fromhex(value)


def operational_build_ref(
    *,
    document_ref: str,
    compiler_contract_ref: str,
    build_key_sha256: str,
) -> str:
    return "build:" + canonical_sha256(
        {
            "operation_ref": _OPERATION_REF,
            "operation_version": _OPERATION_VERSION,
            "document_ref": document_ref,
            "compiler_contract_ref": compiler_contract_ref,
            "build_key_sha256": build_key_sha256,
        }
    )


def load_completed_operational_build(
    cursor: Any,
    *,
    document_ref: str,
    compiler_contract_ref: str,
    build_key_sha256: str,
) -> tuple[str, ...] | None:
    cursor.execute(
        """
        SELECT document_build.build_ref
        FROM execution.document_compilation_build AS document_build
        JOIN execution.build AS build
          ON build.build_ref = document_build.build_ref
        WHERE document_build.document_ref = %s
          AND document_build.compiler_contract_ref = %s
          AND document_build.build_key_sha256 = %s
          AND build.build_state_ref = 'completed'
        """,
        (document_ref, compiler_contract_ref, _digest(build_key_sha256)),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    build_ref = str(row[0])
    cursor.execute(
        """
        SELECT demand_ref
        FROM execution.document_compilation_build_demand
        WHERE build_ref = %s
        ORDER BY demand_ref
        """,
        (build_ref,),
    )
    return tuple(str(item[0]) for item in cursor.fetchall())


def persist_completed_operational_build(
    cursor: Any,
    *,
    document_ref: str,
    compiler_contract_ref: str,
    build_key_sha256: str,
    graph_ref: str,
    demand_refs: Sequence[str],
) -> str:
    build_ref = operational_build_ref(
        document_ref=document_ref,
        compiler_contract_ref=compiler_contract_ref,
        build_key_sha256=build_key_sha256,
    )
    cursor.execute(
        """
        INSERT INTO execution.operation (operation_ref, operation_version)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (_OPERATION_REF, _OPERATION_VERSION),
    )
    cursor.execute(
        """
        INSERT INTO execution.build
            (build_ref, operation_ref, operation_version, build_key_sha256,
             output_ref, build_state_ref)
        VALUES (%s, %s, %s, %s, %s, 'completed')
        ON CONFLICT (build_ref) DO NOTHING
        """,
        (
            build_ref,
            _OPERATION_REF,
            _OPERATION_VERSION,
            _digest(build_key_sha256),
            graph_ref,
        ),
    )
    cursor.execute(
        """
        INSERT INTO execution.document_compilation_build
            (build_ref, document_ref, compiler_contract_ref,
             build_key_sha256, graph_ref)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (build_ref) DO NOTHING
        """,
        (
            build_ref,
            document_ref,
            compiler_contract_ref,
            _digest(build_key_sha256),
            graph_ref,
        ),
    )
    for demand_ref in sorted(set(str(ref) for ref in demand_refs)):
        cursor.execute(
            """
            INSERT INTO execution.document_compilation_build_demand
                (build_ref, demand_ref)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (build_ref, demand_ref),
        )
    return build_ref


__all__ = [
    "load_completed_operational_build",
    "operational_build_ref",
    "persist_completed_operational_build",
]
