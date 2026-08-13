"""Set-based graph, factor-revision, and licensed-span persistence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.algebra.revision_identity import (
    factor_revision_payload,
    factor_revision_ref,
)
from src.storage.postgres.work_conserving_stage import (
    StagePayload,
    _complete_stage,
    _sha,
    _stage_payloads,
)


def deferred_factor_revision(
    cursor: Any,
    *,
    document_ref: str,
    factor: Mapping[str, Any],
) -> str:
    """Return immutable identity; the resolution lane persists it set-wise."""

    del cursor, document_ref
    return factor_revision_ref(factor)


def _factor_payloads(
    *,
    document_ref: str,
    factors: Sequence[Mapping[str, Any]],
    graph_ref: str | None,
) -> tuple[list[StagePayload], dict[str, str]]:
    payloads: list[StagePayload] = []
    revisions: dict[str, str] = {}
    seen_factors: set[str] = set()
    seen_revisions: set[str] = set()
    seen_alternatives: set[str] = set()
    seen_factor_alternatives: set[tuple[str, str]] = set()
    seen_residuals: set[str] = set()
    for factor in factors:
        factor_ref = str(factor["factor_ref"])
        revision_ref = factor_revision_ref(factor)
        revisions[factor_ref] = revision_ref
        if factor_ref not in seen_factors:
            seen_factors.add(factor_ref)
            payloads.append(
                StagePayload(
                    "factor",
                    texts=(factor_ref, document_ref, str(factor["factor_type"])),
                )
            )
        if revision_ref not in seen_revisions:
            seen_revisions.add(revision_ref)
            payloads.append(
                StagePayload(
                    "factor_revision",
                    texts=(
                        revision_ref,
                        factor_ref,
                        str(factor["closure_state"]),
                    ),
                    byteas=(_sha(factor_revision_payload(factor)),),
                )
            )
        if graph_ref is not None:
            payloads.append(
                StagePayload(
                    "graph_factor",
                    texts=(graph_ref, revision_ref, str(factor["factor_type"])),
                )
            )
        for alternative in factor.get("alternatives") or ():
            alternative_ref = str(alternative["alternative_ref"])
            value = alternative.get("value")
            if alternative_ref not in seen_alternatives:
                seen_alternatives.add(alternative_ref)
                payloads.append(
                    StagePayload(
                        "alternative",
                        texts=(
                            alternative_ref,
                            str(alternative["type_ref"]),
                            (
                                str(value.get("mention_ref"))
                                if isinstance(value, Mapping)
                                and value.get("mention_ref")
                                else None
                            ),
                            None if isinstance(value, Mapping) else str(value),
                            str(
                                alternative.get("authority_state")
                                or "candidate_only"
                            ),
                        ),
                        byteas=(_sha(alternative),),
                    )
                )
            pair = (revision_ref, alternative_ref)
            if pair not in seen_factor_alternatives:
                seen_factor_alternatives.add(pair)
                payloads.append(
                    StagePayload(
                        "factor_alternative",
                        texts=(revision_ref, alternative_ref, "alternative"),
                    )
                )
        for residual in factor.get("residuals") or ():
            residual_ref = f"{revision_ref}:residual:{residual}"
            if residual_ref in seen_residuals:
                continue
            seen_residuals.add(residual_ref)
            payloads.append(
                StagePayload(
                    "residual",
                    texts=(residual_ref, revision_ref, str(residual), "open"),
                    byteas=(
                        _sha(
                            {
                                "factor_revision_ref": revision_ref,
                                "residual": residual,
                            }
                        ),
                    ),
                )
            )
    return payloads, revisions


def persist_pnf_graph_work_conserving(
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
            row.get("closure_state")
            in {"locally_closed", "closed", "not_required"}
            for row in factors
        )
        else "open"
    )
    payloads, revisions = _factor_payloads(
        document_ref=document_ref,
        factors=factors,
        graph_ref=graph_ref,
    )
    stage_ref = _stage_payloads(
        cursor,
        family_ref="pnf_graph",
        lane_ref="graph",
        payloads=payloads,
    )
    statements = 0
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
    statements += 1
    for statement in (
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
        INSERT INTO pnf.graph_factor_revision
            (graph_ref, factor_revision_ref, graph_role_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'graph_factor'
        ON CONFLICT DO NOTHING
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
    ):
        cursor.execute(statement, (stage_ref,))
        statements += 1
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=statements)
    return revisions


def persist_licensed_spans_work_conserving(
    cursor: Any,
    *,
    document_ref: str,
    mentions: Sequence[Mapping[str, Any]],
) -> None:
    payloads = [
        StagePayload(
            "licensed_span",
            texts=(str(row["mention_ref"]), document_ref, "licensed_mention"),
            ints=(
                int(row["start_char"]),
                int(row["end_char"]),
                int(row["start_token"]),
                int(row["end_token"]),
            ),
        )
        for row in mentions
    ]
    stage_ref = _stage_payloads(
        cursor,
        family_ref="licensed_spans",
        lane_ref="annotation",
        payloads=payloads,
    )
    cursor.execute(
        """
        INSERT INTO corpus.span
            (span_ref, document_ref, start_char, end_char, start_token,
             end_token, span_type_ref)
        SELECT text_01, text_02, int_01, int_02, int_03, int_04, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'licensed_span'
        ON CONFLICT (span_ref) DO NOTHING
        """,
        (stage_ref,),
    )
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=1)


__all__ = [
    "deferred_factor_revision",
    "persist_licensed_spans_work_conserving",
    "persist_pnf_graph_work_conserving",
]
