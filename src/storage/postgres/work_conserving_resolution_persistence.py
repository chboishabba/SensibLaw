"""Set-based evidence, demand, meet, and refinement persistence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.algebra.revision_identity import factor_revision_ref
from src.storage.postgres.work_conserving_graph_persistence import (
    _factor_payloads,
)
from src.storage.postgres.work_conserving_stage import (
    StagePayload,
    _complete_stage,
    _runtime,
    _sha,
    _stage_payloads,
)


def _resolution_payloads(
    *,
    factor_revisions: Mapping[str, str],
    demands: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    meets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
) -> list[StagePayload]:
    payloads: list[StagePayload] = []
    resulting_factors = tuple(
        row["resulting_factor"]
        for row in refinements
        if isinstance(row.get("resulting_factor"), Mapping)
    )
    factor_rows, _ = _factor_payloads(
        document_ref=_runtime().document_ref,
        factors=resulting_factors,
        graph_ref=None,
    )
    payloads.extend(factor_rows)
    for row in evidence:
        evidence_ref = str(row["evidence_ref"])
        payloads.append(
            StagePayload(
                "evidence",
                texts=(
                    evidence_ref,
                    str(row["document_ref"]),
                    str(row["evidence_type"]),
                    str(row.get("relation") or ""),
                ),
                byteas=(_sha(row),),
            )
        )
        payloads.extend(
            StagePayload(
                "evidence_subject", texts=(evidence_ref, str(subject_ref))
            )
            for subject_ref in row.get("subject_refs") or ()
        )
    for row in demands:
        demand_ref = str(row["demand_ref"])
        factor_ref = str(row["factor_ref"])
        scope_ref = str(
            row.get("scope_ref")
            or row.get("document_scope")
            or row.get("document_ref")
            or "document_local"
        )
        payloads.append(
            StagePayload(
                "demand",
                texts=(
                    demand_ref,
                    factor_ref,
                    factor_revisions.get(factor_ref),
                    str(
                        row.get("subject_kind")
                        or row.get("factor_type")
                        or "unknown"
                    ),
                    (
                        str(row["formal_role"])
                        if row.get("formal_role") is not None
                        else None
                    ),
                    scope_ref,
                    str(row.get("budget_class") or row.get("budget") or "default"),
                    "open",
                ),
                byteas=(_sha(row.get("semantic_key") or row),),
            )
        )
        payloads.extend(
            StagePayload("demand_facet", texts=(demand_ref, str(facet)))
            for facet in row.get("requested_facets") or ()
        )
    for row in meets:
        meet_ref = str(row["meet_ref"])
        payloads.append(
            StagePayload(
                "meet",
                texts=(
                    meet_ref,
                    str(row["left_ref"]),
                    str(row["right_ref"]),
                    str(row["meet_type"]),
                    str(row["state"]),
                ),
                byteas=(_sha(row),),
            )
        )
        payloads.extend(
            StagePayload("meet_evidence", texts=(meet_ref, str(evidence_ref)))
            for evidence_ref in row.get("evidence_refs") or ()
        )
    for row in refinements:
        prior = row["prior_factor"]
        resulting = row["resulting_factor"]
        refinement_ref = str(row["refinement_ref"])
        payloads.append(
            StagePayload(
                "refinement",
                texts=(
                    refinement_ref,
                    str(prior["factor_ref"]),
                    factor_revision_ref(prior),
                    factor_revision_ref(resulting),
                ),
                byteas=(_sha(row),),
            )
        )
        for transition_type, key in (
            ("added", "added_alternative_refs"),
            ("retained", "retained_alternative_refs"),
            ("rejected", "rejected_alternative_refs"),
        ):
            payloads.extend(
                StagePayload(
                    "refinement_alternative_transition",
                    texts=(refinement_ref, str(alternative_ref), transition_type),
                )
                for alternative_ref in row.get(key) or ()
            )
        payloads.extend(
            StagePayload(
                "refinement_residual_transition",
                texts=(
                    refinement_ref,
                    str(transition["residual_ref"]),
                    str(transition.get("prior_state") or ""),
                    str(transition.get("resulting_state") or ""),
                ),
            )
            for transition in row.get("residual_transitions") or ()
        )
    return payloads


def persist_resolution_artifacts_work_conserving(
    cursor: Any,
    *,
    factor_revisions: Mapping[str, str],
    demands: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    meets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    payloads = _resolution_payloads(
        factor_revisions=factor_revisions,
        demands=demands,
        evidence=evidence,
        meets=meets,
        refinements=refinements,
    )
    stage_ref = _stage_payloads(
        cursor,
        family_ref="resolution_artifacts",
        lane_ref="resolution",
        payloads=payloads,
    )
    statements = 0
    statements_sql = (
        """
        INSERT INTO algebra.factor (factor_ref, document_ref, factor_type_ref)
        SELECT DISTINCT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor'
        ON CONFLICT (factor_ref) DO NOTHING
        """,
        """
        INSERT INTO algebra.factor_revision
            (factor_revision_ref, factor_ref, closure_state_ref, factor_sha256)
        SELECT DISTINCT text_01, text_02, text_03, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor_revision'
        ON CONFLICT (factor_revision_ref) DO NOTHING
        """,
        """
        INSERT INTO algebra.alternative
            (alternative_ref, type_ref, value_ref, value_literal,
             authority_state_ref, alternative_sha256)
        SELECT DISTINCT text_01, text_02, text_03, text_04, text_05, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'alternative'
        ON CONFLICT (alternative_ref) DO NOTHING
        """,
        """
        INSERT INTO algebra.factor_revision_alternative
            (factor_revision_ref, alternative_ref, alternative_state_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor_alternative'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO algebra.residual
            (residual_ref, target_ref, residual_type_ref,
             residual_state_ref, residual_sha256)
        SELECT text_01, text_02, text_03, text_04, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'residual'
        ON CONFLICT (residual_ref) DO NOTHING
        """,
        """
        INSERT INTO evidence.local_evidence
            (evidence_ref, document_ref, evidence_type_ref, relation_ref,
             evidence_sha256)
        SELECT text_01, text_02, text_03, text_04, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'evidence'
        ON CONFLICT (evidence_ref) DO NOTHING
        """,
        """
        INSERT INTO evidence.local_evidence_subject (evidence_ref, subject_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'evidence_subject'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.demand
            (demand_ref, factor_ref, factor_revision_ref, subject_kind_ref,
             formal_role_ref, scope_ref, semantic_key_sha256,
             budget_class_ref, demand_state_ref)
        SELECT text_01, text_02, text_03, text_04, text_05, text_06,
               bytea_01, text_07, text_08
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'demand'
        ON CONFLICT (demand_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.demand_facet (demand_ref, facet_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'demand_facet'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.typed_meet
            (meet_ref, left_ref, right_ref, meet_type_ref, meet_state_ref,
             meet_sha256)
        SELECT text_01, text_02, text_03, text_04, text_05, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'meet'
        ON CONFLICT (meet_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.meet_evidence (meet_ref, evidence_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'meet_evidence'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.refinement
            (refinement_ref, factor_ref, prior_factor_revision_ref,
             resulting_factor_revision_ref, refinement_sha256)
        SELECT text_01, text_02, text_03, text_04, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'refinement'
        ON CONFLICT (refinement_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.refinement_alternative_transition
            (refinement_ref, alternative_ref, transition_type_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s
          AND row_kind_ref = 'refinement_alternative_transition'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.refinement_residual_transition
            (refinement_ref, residual_ref, prior_state_ref, resulting_state_ref)
        SELECT text_01, text_02, text_03, text_04
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s
          AND row_kind_ref = 'refinement_residual_transition'
        ON CONFLICT DO NOTHING
        """,
    )
    for statement in statements_sql:
        cursor.execute(statement, (stage_ref,))
        statements += 1
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=statements)
    return tuple(sorted(str(row["demand_ref"]) for row in demands))


__all__ = ["persist_resolution_artifacts_work_conserving"]
