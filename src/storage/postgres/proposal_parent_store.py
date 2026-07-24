"""Parent-row persistence required before fibred proposal extensions."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def persist_factor_proposal_parents(
    cursor: Any,
    proposals: Sequence[Mapping[str, Any]],
) -> None:
    if not proposals:
        return
    cursor.executemany(
        """
        INSERT INTO pnf_factor_proposal
            (proposal_ref, proposal_digest, document_ref, source_revision_ref,
             factor_type_ref, structural_signature, producer_contract,
             declaration_revision, source_span_refs, input_observation_refs,
             dependency_factor_refs, role_bindings, qualifier_state,
             candidate_payload, residuals, authority)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                %s::jsonb, %s::jsonb, 'candidate_only')
        ON CONFLICT (proposal_ref) DO NOTHING
        """,
        [
            (
                row["proposal_ref"], row["proposal_digest"], row["document_ref"],
                row["source_revision_ref"], row["factor_type_ref"],
                row["structural_signature"], row["producer_contract"],
                row["declaration_revision"], _json(row.get("source_span_refs") or ()),
                _json(row.get("input_observation_refs") or ()),
                _json(row.get("dependency_factor_refs") or ()),
                _json(row.get("role_bindings") or {}),
                _json(row.get("qualifier_state") or {}),
                _json(row.get("candidate_payload") or {}),
                _json(row.get("residuals") or ()),
            )
            for row in proposals
        ],
    )


__all__ = ["persist_factor_proposal_parents"]
