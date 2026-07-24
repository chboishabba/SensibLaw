"""Batched persistence for PNF graphs and resolution child rows."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.factor_revision_store import (
    factor_revision_payload,
    factor_revision_ref,
)


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def persist_pnf_graph_batched(
    cursor: Any,
    *,
    document_ref: str,
    graph: Mapping[str, Any],
) -> dict[str, str]:
    graph_ref = str(graph["graph_ref"])
    factors = tuple(graph.get("factors") or ())
    graph_state = (
        "locally_closed"
        if all(
            row.get("closure_state") in {"locally_closed", "closed", "not_required"}
            for row in factors
        )
        else "open"
    )
    cursor.execute(
        """
        INSERT INTO pnf.graph
            (graph_ref, document_ref, graph_type_ref, schema_version_ref,
             closure_state_ref, graph_sha256)
        VALUES (%s, %s, 'generic.factor_graph', 'v0_1', %s, %s)
        ON CONFLICT (graph_ref) DO NOTHING
        """,
        (graph_ref, document_ref, graph_state, _sha(graph)),
    )
    revisions = {
        str(factor["factor_ref"]): factor_revision_ref(factor) for factor in factors
    }
    if factors:
        cursor.executemany(
            """
            INSERT INTO algebra.factor (factor_ref, document_ref, factor_type_ref)
            VALUES (%s, %s, %s) ON CONFLICT (factor_ref) DO NOTHING
            """,
            [
                (str(factor["factor_ref"]), document_ref, str(factor["factor_type"]))
                for factor in factors
            ],
        )
        cursor.executemany(
            """
            INSERT INTO algebra.factor_revision
                (factor_revision_ref, factor_ref, closure_state_ref, factor_sha256)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (factor_revision_ref) DO NOTHING
            """,
            [
                (
                    revisions[str(factor["factor_ref"])],
                    str(factor["factor_ref"]),
                    str(factor["closure_state"]),
                    _sha(factor_revision_payload(factor)),
                )
                for factor in factors
            ],
        )
        cursor.executemany(
            """
            INSERT INTO pnf.graph_factor_revision
                (graph_ref, factor_revision_ref, graph_role_ref)
            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """,
            [
                (
                    graph_ref,
                    revisions[str(factor["factor_ref"])],
                    str(factor["factor_type"]),
                )
                for factor in factors
            ],
        )
    alternatives = [
        (factor, alternative)
        for factor in factors
        for alternative in factor.get("alternatives") or ()
    ]
    if alternatives:
        cursor.executemany(
            """
            INSERT INTO algebra.alternative
                (alternative_ref, type_ref, value_ref, value_literal,
                 authority_state_ref, alternative_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (alternative_ref) DO NOTHING
            """,
            [
                (
                    str(alternative["alternative_ref"]),
                    str(alternative["type_ref"]),
                    (
                        str(alternative.get("value", {}).get("mention_ref"))
                        if isinstance(alternative.get("value"), Mapping)
                        and alternative.get("value", {}).get("mention_ref")
                        else None
                    ),
                    (
                        None
                        if isinstance(alternative.get("value"), Mapping)
                        else str(alternative.get("value"))
                    ),
                    str(alternative.get("authority_state") or "candidate_only"),
                    _sha(alternative),
                )
                for _, alternative in alternatives
            ],
        )
        cursor.executemany(
            """
            INSERT INTO algebra.factor_revision_alternative
                (factor_revision_ref, alternative_ref, alternative_state_ref)
            VALUES (%s, %s, 'alternative') ON CONFLICT DO NOTHING
            """,
            [
                (
                    revisions[str(factor["factor_ref"])],
                    str(alternative["alternative_ref"]),
                )
                for factor, alternative in alternatives
            ],
        )
    residual_rows = [
        (
            f"{revisions[str(factor['factor_ref'])]}:residual:{residual}",
            revisions[str(factor["factor_ref"])],
            str(residual),
            _sha(
                {
                    "factor_revision_ref": revisions[str(factor["factor_ref"])],
                    "residual": residual,
                }
            ),
        )
        for factor in factors
        for residual in factor.get("residuals") or ()
    ]
    if residual_rows:
        cursor.executemany(
            """
            INSERT INTO algebra.residual
                (residual_ref, target_ref, residual_type_ref,
                 residual_state_ref, residual_sha256)
            VALUES (%s, %s, %s, 'open', %s)
            ON CONFLICT (residual_ref) DO NOTHING
            """,
            residual_rows,
        )
    return revisions


def persist_resolution_artifacts_batched(
    cursor: Any,
    *,
    factor_revisions: Mapping[str, str],
    demands: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    meets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    if evidence:
        cursor.executemany(
            """
            INSERT INTO evidence.local_evidence
                (evidence_ref, document_ref, evidence_type_ref, relation_ref,
                 evidence_sha256)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (evidence_ref) DO NOTHING
            """,
            [
                (
                    str(row["evidence_ref"]),
                    str(row["document_ref"]),
                    str(row["evidence_type"]),
                    str(row.get("relation") or ""),
                    _sha(row),
                )
                for row in evidence
            ],
        )
        subjects = [
            (str(row["evidence_ref"]), str(subject_ref))
            for row in evidence
            for subject_ref in row.get("subject_refs") or ()
        ]
        if subjects:
            cursor.executemany(
                """
                INSERT INTO evidence.local_evidence_subject
                    (evidence_ref, subject_ref)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                subjects,
            )

    demand_rows = []
    facet_rows = []
    for row in demands:
        demand_ref = str(row["demand_ref"])
        factor_ref = str(row["factor_ref"])
        scope_ref = str(
            row.get("scope_ref")
            or row.get("document_scope")
            or row.get("document_ref")
            or "document_local"
        )
        demand_rows.append(
            (
                demand_ref,
                factor_ref,
                factor_revisions.get(factor_ref),
                str(row.get("subject_kind") or row.get("factor_type") or "unknown"),
                row.get("formal_role"),
                scope_ref,
                _sha(row.get("semantic_key") or row),
                str(row.get("budget_class") or row.get("budget") or "default"),
            )
        )
        facet_rows.extend(
            (demand_ref, str(facet)) for facet in row.get("requested_facets") or ()
        )
    if demand_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.demand
                (demand_ref, factor_ref, factor_revision_ref, subject_kind_ref,
                 formal_role_ref, scope_ref, semantic_key_sha256,
                 budget_class_ref, demand_state_ref)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open')
            ON CONFLICT (demand_ref) DO NOTHING
            """,
            demand_rows,
        )
    if facet_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.demand_facet (demand_ref, facet_ref)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
            """,
            facet_rows,
        )

    if meets:
        cursor.executemany(
            """
            INSERT INTO resolution.typed_meet
                (meet_ref, left_ref, right_ref, meet_type_ref, meet_state_ref,
                 meet_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (meet_ref) DO NOTHING
            """,
            [
                (
                    str(row["meet_ref"]),
                    str(row["left_ref"]),
                    str(row["right_ref"]),
                    str(row["meet_type"]),
                    str(row["state"]),
                    _sha(row),
                )
                for row in meets
            ],
        )
        meet_evidence = [
            (str(row["meet_ref"]), str(evidence_ref))
            for row in meets
            for evidence_ref in row.get("evidence_refs") or ()
        ]
        if meet_evidence:
            cursor.executemany(
                """
                INSERT INTO resolution.meet_evidence (meet_ref, evidence_ref)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                meet_evidence,
            )

    revision_rows = []
    refinement_rows = []
    alternative_transition_rows = []
    residual_transition_rows = []
    for row in refinements:
        prior = row["prior_factor"]
        resulting = row["resulting_factor"]
        factor_ref = str(prior["factor_ref"])
        prior_revision_ref = factor_revision_ref(prior)
        resulting_revision_ref = factor_revision_ref(resulting)
        revision_rows.append(
            (
                resulting_revision_ref,
                factor_ref,
                str(resulting["closure_state"]),
                _sha(factor_revision_payload(resulting)),
            )
        )
        refinement_rows.append(
            (
                str(row["refinement_ref"]),
                factor_ref,
                prior_revision_ref,
                resulting_revision_ref,
                _sha(row),
            )
        )
        for transition_type, key in (
            ("added", "added_alternative_refs"),
            ("retained", "retained_alternative_refs"),
            ("rejected", "rejected_alternative_refs"),
        ):
            alternative_transition_rows.extend(
                (str(row["refinement_ref"]), str(ref), transition_type)
                for ref in row.get(key) or ()
            )
        residual_transition_rows.extend(
            (
                str(row["refinement_ref"]),
                str(transition["residual_ref"]),
                str(transition.get("prior_state") or ""),
                str(transition.get("resulting_state") or ""),
            )
            for transition in row.get("residual_transitions") or ()
        )
    if revision_rows:
        cursor.executemany(
            """
            INSERT INTO algebra.factor_revision
                (factor_revision_ref, factor_ref, closure_state_ref, factor_sha256)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (factor_revision_ref) DO NOTHING
            """,
            revision_rows,
        )
        cursor.executemany(
            """
            INSERT INTO resolution.refinement
                (refinement_ref, factor_ref, prior_factor_revision_ref,
                 resulting_factor_revision_ref, refinement_sha256)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (refinement_ref) DO NOTHING
            """,
            refinement_rows,
        )
    if alternative_transition_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.refinement_alternative_transition
                (refinement_ref, alternative_ref, transition_type_ref)
            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """,
            alternative_transition_rows,
        )
    if residual_transition_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.refinement_residual_transition
                (refinement_ref, residual_ref, prior_state_ref, resulting_state_ref)
            VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """,
            residual_transition_rows,
        )
    return tuple(sorted(str(row["demand_ref"]) for row in demands))


__all__ = ["persist_pnf_graph_batched", "persist_resolution_artifacts_batched"]
