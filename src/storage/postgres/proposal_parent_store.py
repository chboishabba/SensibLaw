"""Typed parent-row persistence for factor proposals.

Legacy callers may still supply mapping-shaped proposal views, but persistence
is relational: scalar columns, typed value trees, role rows and ordered
reference rows.  No proposal authority is serialized through JSON or JSONB.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_fields_sha256
from src.storage.postgres.typed_value_store import persist_typed_value


def _texts(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or values is None:
        return ()
    return tuple(
        sorted({str(value) for value in values if str(value)})
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _digest_bytes(value: object, *fallback: object) -> bytes:
    text = str(value or "").strip()
    if len(text) == 64:
        try:
            return bytes.fromhex(text)
        except ValueError:
            pass
    return bytes.fromhex(canonical_fields_sha256(*fallback))


def _persist_refs(
    cursor: Any,
    *,
    proposal_ref: str,
    ref_kind: str,
    values: tuple[str, ...],
) -> None:
    if not values:
        return
    cursor.executemany(
        """
        INSERT INTO execution.semantic_factor_proposal_ref
            (proposal_ref, ref_kind, ordinal, value_ref)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        [
            (proposal_ref, ref_kind, ordinal, value)
            for ordinal, value in enumerate(values)
        ],
    )


def persist_factor_proposal_parents(
    cursor: Any,
    proposals: Sequence[Mapping[str, Any]],
) -> None:
    """Persist mapping-shaped compatibility views into typed proposal tables."""

    for row in proposals:
        proposal_ref = str(row.get("proposal_ref") or "").strip()
        document_ref = str(row.get("document_ref") or "").strip()
        source_revision_ref = str(
            row.get("source_revision_ref") or ""
        ).strip()
        factor_type_ref = str(row.get("factor_type_ref") or "").strip()
        structural_signature = str(
            row.get("structural_signature") or ""
        ).strip()
        producer_contract = str(
            row.get("producer_contract") or ""
        ).strip()
        declaration_revision = str(
            row.get("declaration_revision") or ""
        ).strip()
        if not all(
            (
                proposal_ref,
                document_ref,
                source_revision_ref,
                factor_type_ref,
                structural_signature,
                producer_contract,
                declaration_revision,
            )
        ):
            raise ValueError("typed proposal persistence requires stable core fields")

        scope_ref = str(row.get("scope_ref") or "document-global")
        statement_role = str(row.get("statement_role") or "main")
        coordinate_kind = str(row.get("coordinate_kind") or "object")
        fibre_kind = str(row.get("fibre_kind") or "proposal")
        derivation_role = str(row.get("derivation_role") or "support")
        producer_scope = str(row.get("producer_scope") or "document")
        operation_contract = str(
            row.get("operation_contract") or producer_contract
        )
        support_state = str(row.get("support_state") or "candidate")
        source_span_refs = _texts(row.get("source_span_refs"))
        observation_refs = _texts(row.get("input_observation_refs"))
        dependency_refs = _texts(row.get("dependency_factor_refs"))
        residual_refs = _texts(row.get("residuals"))
        ontology_axis_refs = _texts(row.get("ontology_axis_refs"))
        transport_refs = _texts(row.get("transport_refs"))
        assumption_refs = _texts(row.get("assumptions"))
        coverage_refs = _texts(row.get("coverage_requirements"))
        role_bindings = _mapping(row.get("role_bindings"))
        qualifier_state = _mapping(row.get("qualifier_state"))
        candidate_payload = _mapping(row.get("candidate_payload"))
        execution_metadata = _mapping(row.get("execution_metadata"))
        semantic_coordinate_ref = str(
            row.get("semantic_coordinate_ref")
            or "semantic-coordinate:"
            + canonical_fields_sha256(
                document_ref,
                scope_ref,
                statement_role,
                coordinate_kind,
                factor_type_ref,
                source_span_refs,
            )
        )
        qualifier_root = persist_typed_value(cursor, qualifier_state)
        candidate_root = persist_typed_value(cursor, candidate_payload)
        execution_root = persist_typed_value(cursor, execution_metadata)
        proposal_digest = _digest_bytes(
            row.get("proposal_digest"),
            proposal_ref,
            document_ref,
            source_revision_ref,
            semantic_coordinate_ref,
            factor_type_ref,
            structural_signature,
            producer_contract,
            declaration_revision,
            source_span_refs,
            observation_refs,
            dependency_refs,
            tuple(sorted((str(key), str(value)) for key, value in role_bindings.items())),
            qualifier_state,
            candidate_payload,
            residual_refs,
        )

        cursor.execute(
            """
            INSERT INTO execution.semantic_factor_proposal
                (proposal_ref, document_ref, source_revision_ref,
                 semantic_coordinate_ref, scope_ref, statement_role,
                 coordinate_kind, fibre_kind, derivation_role, factor_type_ref,
                 structural_signature, producer_contract, producer_scope,
                 operation_contract, declaration_revision, support_state,
                 confidence, qualifier_root_ref, candidate_root_ref,
                 execution_root_ref, proposal_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (proposal_ref) DO NOTHING
            """,
            (
                proposal_ref,
                document_ref,
                source_revision_ref,
                semantic_coordinate_ref,
                scope_ref,
                statement_role,
                coordinate_kind,
                fibre_kind,
                derivation_role,
                factor_type_ref,
                structural_signature,
                producer_contract,
                producer_scope,
                operation_contract,
                declaration_revision,
                support_state,
                row.get("confidence"),
                qualifier_root,
                candidate_root,
                execution_root,
                proposal_digest,
            ),
        )
        for role_ref, value_ref in sorted(
            (str(key), str(value)) for key, value in role_bindings.items()
        ):
            cursor.execute(
                """
                INSERT INTO execution.semantic_factor_proposal_role
                    (proposal_ref, role_ref, value_ref)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (proposal_ref, role_ref, value_ref),
            )
        for ref_kind, values in (
            ("source_span", source_span_refs),
            ("input_observation", observation_refs),
            ("dependency_factor", dependency_refs),
            ("residual", residual_refs),
            ("ontology_axis", ontology_axis_refs),
            ("transport", transport_refs),
            ("assumption", assumption_refs),
            ("coverage", coverage_refs),
        ):
            _persist_refs(
                cursor,
                proposal_ref=proposal_ref,
                ref_kind=ref_kind,
                values=values,
            )


__all__ = ["persist_factor_proposal_parents"]
