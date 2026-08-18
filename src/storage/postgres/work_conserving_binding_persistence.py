"""Set-based PNF binding-candidate persistence and validation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.storage.postgres.work_conserving_stage import (
    StagePayload,
    _complete_stage,
    _stage_payloads,
    _text_sha,
)


def _binding_payloads(
    *,
    candidate_sets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
    factor_revisions: Mapping[str, str],
    factor_anchors: Sequence[Mapping[str, Any]],
    builds: Sequence[Mapping[str, Any]],
    meets: Sequence[Mapping[str, Any]],
    demands: Sequence[Mapping[str, Any]],
) -> list[StagePayload]:
    payloads: list[StagePayload] = []
    for row in factor_anchors:
        factor_ref = str(row["factor_ref"])
        revision_ref = factor_revisions.get(factor_ref)
        if revision_ref is None:
            raise ValueError(
                "binding factor anchor references an unpersisted factor revision: "
                f"document_ref={row['document_ref']} factor_ref={factor_ref}"
            )
        payloads.append(
            StagePayload(
                "factor_anchor",
                texts=(
                    revision_ref,
                    str(row["document_ref"]),
                    (
                        str(row["clause_ref"])
                        if row.get("clause_ref") is not None
                        else None
                    ),
                    str(row["pnf_kind_ref"]),
                    str(row.get("morphology_sha256") or ""),
                    (
                        str(row["discourse_unit_ref"])
                        if row.get("discourse_unit_ref") is not None
                        else None
                    ),
                    (
                        str(row["reporting_scope_ref"])
                        if row.get("reporting_scope_ref") is not None
                        else None
                    ),
                    (
                        str(row["coordination_group_ref"])
                        if row.get("coordination_group_ref") is not None
                        else None
                    ),
                    (
                        str(row["parser_pos"])
                        if row.get("parser_pos") is not None
                        else None
                    ),
                    (
                        str(row["parser_dependency"])
                        if row.get("parser_dependency") is not None
                        else None
                    ),
                ),
                ints=(
                    (
                        int(row["sentence_index"])
                        if row.get("sentence_index") is not None
                        else None
                    ),
                    int(row["start_token"]),
                    int(row["end_token"]),
                    (
                        int(row["paragraph_index"])
                        if row.get("paragraph_index") is not None
                        else None
                    ),
                    (
                        int(row["quotation_depth"])
                        if row.get("quotation_depth") is not None
                        else None
                    ),
                ),
            )
        )
        for feature_ref, values in sorted((row.get("morphology") or {}).items()):
            payloads.extend(
                StagePayload(
                    "factor_morphology",
                    texts=(revision_ref, str(feature_ref), str(value_ref)),
                )
                for value_ref in sorted(str(value) for value in values)
            )
    builds_by_set = {str(row["candidate_set_ref"]): dict(row) for row in builds}
    known_sets: set[str] = set()
    for row in candidate_sets:
        candidate_set_ref = str(row["candidate_set_ref"])
        known_sets.add(candidate_set_ref)
        reference_factor_ref = str(row["reference_factor_ref"])
        reference_revision = factor_revisions.get(reference_factor_ref)
        if reference_revision is None:
            raise ValueError(
                "binding candidate set references an unpersisted factor revision"
            )
        payloads.append(
            StagePayload(
                "candidate_set",
                texts=(
                    candidate_set_ref,
                    str(row["document_ref"]),
                    reference_factor_ref,
                    reference_revision,
                    str(row["referential_type_ref"]),
                    str(row["accessibility_declaration_ref"]),
                    str(row["compatibility_declaration_ref"]),
                    str(row["generator_build_ref"]),
                    str(row["compatibility_state"]),
                    _text_sha(row),
                ),
                ints=(int(row["member_count"]),),
            )
        )
        build = builds_by_set.get(candidate_set_ref) or {
            "generator_build_ref": row["generator_build_ref"],
            "candidate_set_ref": candidate_set_ref,
            "reference_factor_revision_ref": reference_revision,
            "document_pnf_index_ref": "",
            "accessibility_declaration_ref": row["accessibility_declaration_ref"],
            "compatibility_declaration_ref": row["compatibility_declaration_ref"],
            "referential_type_ref": row["referential_type_ref"],
        }
        build = {**build, "reference_factor_revision_ref": reference_revision}
        build_identity = {
            "generator_build_ref": build["generator_build_ref"],
            "reference_factor_revision_ref": build["reference_factor_revision_ref"],
            "document_pnf_index_ref": build.get("document_pnf_index_ref"),
            "accessibility_declaration_ref": build["accessibility_declaration_ref"],
            "compatibility_declaration_ref": build["compatibility_declaration_ref"],
            "referential_type_ref": build["referential_type_ref"],
        }
        payloads.append(
            StagePayload(
                "candidate_build",
                texts=(
                    str(build["generator_build_ref"]),
                    candidate_set_ref,
                    reference_revision,
                    str(build.get("document_pnf_index_ref") or ""),
                    str(build["accessibility_declaration_ref"]),
                    str(build["compatibility_declaration_ref"]),
                    str(build["referential_type_ref"]),
                    _text_sha(build_identity),
                    "completed",
                ),
            )
        )
        for ordinal, member in enumerate(row.get("members") or ()):
            assessment_ref = str(member["compatibility_assessment_ref"])
            candidate_factor_ref = str(member["candidate_factor_ref"])
            accessibility_path_ref = str(member["accessibility_path_ref"])
            payloads.append(
                StagePayload(
                    "compatibility_assessment",
                    texts=(
                        assessment_ref,
                        candidate_set_ref,
                        candidate_factor_ref,
                        str(member["compatibility_state"]),
                        accessibility_path_ref,
                        _text_sha(member),
                    ),
                )
            )
            payloads.append(
                StagePayload(
                    "candidate_member",
                    texts=(
                        candidate_set_ref,
                        candidate_factor_ref,
                        assessment_ref,
                        accessibility_path_ref,
                    ),
                    ints=(ordinal,),
                )
            )
        payloads.extend(
            StagePayload(
                "exclusion_summary",
                texts=(
                    candidate_set_ref,
                    str(summary["reason_ref"]),
                    str(summary["generator_build_ref"]),
                ),
                ints=(int(summary["excluded_count"]),),
            )
            for summary in row.get("exclusion_summaries") or ()
        )
    payloads.extend(
        StagePayload(
            "refinement_candidate_set",
            texts=(str(row["refinement_ref"]), str(candidate_set_ref)),
        )
        for row in refinements
        for candidate_set_ref in row.get("candidate_set_refs") or ()
        if str(candidate_set_ref) in known_sets
    )
    payloads.extend(
        StagePayload(
            "meet_candidate_set",
            texts=(str(row["meet_ref"]), str(candidate_set_ref)),
        )
        for row in meets
        for candidate_set_ref in row.get("candidate_set_refs") or ()
        if str(candidate_set_ref) in known_sets
    )
    payloads.extend(
        StagePayload(
            "demand_candidate_set",
            texts=(str(row["demand_ref"]), str(candidate_set_ref)),
        )
        for row in demands
        for candidate_set_ref in row.get("candidate_set_refs") or ()
        if str(candidate_set_ref) in known_sets
    )
    return payloads


def _publish_binding_stage(cursor: Any, *, stage_ref: str) -> int:
    statements_sql = (
        """
        INSERT INTO pnf.factor_anchor
            (factor_revision_ref, document_ref, sentence_index, clause_ref,
             start_token, end_token, pnf_kind_ref, morphology_sha256,
             discourse_unit_ref, paragraph_index, quotation_depth,
             reporting_scope_ref, coordination_group_ref, parser_pos_ref,
             parser_dependency_ref)
        SELECT text_01, text_02, int_01, text_03, int_02, int_03, text_04,
               text_05, text_06, int_04, int_05, text_07, text_08,
               text_09, text_10
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor_anchor'
        ON CONFLICT (factor_revision_ref) DO UPDATE SET
            sentence_index = EXCLUDED.sentence_index,
            clause_ref = EXCLUDED.clause_ref,
            start_token = EXCLUDED.start_token,
            end_token = EXCLUDED.end_token,
            pnf_kind_ref = EXCLUDED.pnf_kind_ref,
            morphology_sha256 = EXCLUDED.morphology_sha256,
            discourse_unit_ref = EXCLUDED.discourse_unit_ref,
            paragraph_index = EXCLUDED.paragraph_index,
            quotation_depth = EXCLUDED.quotation_depth,
            reporting_scope_ref = EXCLUDED.reporting_scope_ref,
            coordination_group_ref = EXCLUDED.coordination_group_ref,
            parser_pos_ref = EXCLUDED.parser_pos_ref,
            parser_dependency_ref = EXCLUDED.parser_dependency_ref
        """,
        """
        INSERT INTO pnf.factor_morphology
            (factor_revision_ref, feature_ref, value_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor_morphology'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.binding_candidate_set
            (candidate_set_ref, document_ref, reference_factor_ref,
             reference_factor_revision_ref, referential_type_ref,
             accessibility_declaration_ref, compatibility_declaration_ref,
             generator_build_ref, compatibility_state_ref, member_count,
             candidate_set_sha256)
        SELECT text_01, text_02, text_03, text_04, text_05, text_06,
               text_07, text_08, text_09, int_01, text_10
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'candidate_set'
        ON CONFLICT (candidate_set_ref) DO NOTHING
        """,
        """
        INSERT INTO execution.binding_candidate_set_build
            (generator_build_ref, candidate_set_ref,
             reference_factor_revision_ref, document_pnf_index_ref,
             accessibility_declaration_ref, compatibility_declaration_ref,
             referential_type_ref, build_key_sha256, build_state_ref)
        SELECT text_01, text_02, text_03, text_04, text_05, text_06,
               text_07, text_08, text_09
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'candidate_build'
        ON CONFLICT (generator_build_ref) DO UPDATE SET
            candidate_set_ref = EXCLUDED.candidate_set_ref,
            reference_factor_revision_ref = EXCLUDED.reference_factor_revision_ref,
            document_pnf_index_ref = EXCLUDED.document_pnf_index_ref,
            accessibility_declaration_ref = EXCLUDED.accessibility_declaration_ref,
            compatibility_declaration_ref = EXCLUDED.compatibility_declaration_ref,
            referential_type_ref = EXCLUDED.referential_type_ref,
            build_key_sha256 = EXCLUDED.build_key_sha256
        """,
        """
        INSERT INTO resolution.binding_compatibility_assessment
            (compatibility_assessment_ref, candidate_set_ref,
             candidate_factor_ref, compatibility_state_ref,
             accessibility_path_ref, assessment_sha256)
        SELECT text_01, text_02, text_03, text_04, text_05, text_06
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'compatibility_assessment'
        ON CONFLICT (compatibility_assessment_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.binding_candidate_member
            (candidate_set_ref, candidate_factor_ref,
             compatibility_assessment_ref, accessibility_path_ref, ordinal)
        SELECT text_01, text_02, text_03, text_04, int_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'candidate_member'
        ON CONFLICT (candidate_set_ref, candidate_factor_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.binding_exclusion_summary
            (candidate_set_ref, reason_ref, excluded_count, generator_build_ref)
        SELECT text_01, text_02, int_01, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'exclusion_summary'
        ON CONFLICT (candidate_set_ref, reason_ref) DO UPDATE SET
            excluded_count = EXCLUDED.excluded_count,
            generator_build_ref = EXCLUDED.generator_build_ref
        """,
        """
        INSERT INTO resolution.refinement_candidate_set
            (refinement_ref, candidate_set_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'refinement_candidate_set'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.meet_candidate_set (meet_ref, candidate_set_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'meet_candidate_set'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.demand_candidate_set (demand_ref, candidate_set_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'demand_candidate_set'
        ON CONFLICT DO NOTHING
        """,
    )
    for statement in statements_sql:
        cursor.execute(statement, (stage_ref,))
    return len(statements_sql)


def _validate_binding_stage(cursor: Any, *, stage_ref: str) -> None:
    cursor.execute(
        """
        WITH expected AS (
            SELECT text_01 AS candidate_set_ref,
                   text_02 AS candidate_factor_ref
            FROM execution.document_persistence_stage
            WHERE stage_ref = %s AND row_kind_ref = 'candidate_member'
        ),
        actual AS (
            SELECT candidate.text_01 AS candidate_set_ref,
                   query.candidate_factor_ref::text AS candidate_factor_ref
            FROM execution.document_persistence_stage AS candidate
            CROSS JOIN LATERAL resolution.query_binding_candidates(
                candidate.text_04,
                candidate.text_05,
                candidate.text_06,
                candidate.text_07,
                64
            ) AS query
            WHERE candidate.stage_ref = %s
              AND candidate.row_kind_ref = 'candidate_set'
        ),
        delta AS (
            (SELECT candidate_set_ref, candidate_factor_ref, 'missing' AS direction
             FROM expected
             EXCEPT
             SELECT candidate_set_ref, candidate_factor_ref, 'missing'
             FROM actual)
            UNION ALL
            (SELECT candidate_set_ref, candidate_factor_ref, 'unexpected' AS direction
             FROM actual
             EXCEPT
             SELECT candidate_set_ref, candidate_factor_ref, 'unexpected'
             FROM expected)
        )
        SELECT candidate_set_ref, candidate_factor_ref, direction
        FROM delta
        ORDER BY candidate_set_ref, candidate_factor_ref, direction
        LIMIT 1
        """,
        (stage_ref, stage_ref),
    )
    mismatch = cursor.fetchone()
    if mismatch is not None:
        raise ValueError(
            "PostgreSQL structural binding index disagrees with staged membership: "
            f"candidate_set_ref={mismatch[0]} candidate_factor_ref={mismatch[1]} "
            f"direction={mismatch[2]}"
        )


def persist_binding_candidate_sets_work_conserving(
    cursor: Any,
    *,
    candidate_sets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
    factor_revisions: Mapping[str, str],
    factor_anchors: Sequence[Mapping[str, Any]] = (),
    builds: Sequence[Mapping[str, Any]] = (),
    meets: Sequence[Mapping[str, Any]] = (),
    demands: Sequence[Mapping[str, Any]] = (),
    validate_indexed_query: bool = False,
) -> None:
    payloads = _binding_payloads(
        candidate_sets=candidate_sets,
        refinements=refinements,
        factor_revisions=factor_revisions,
        factor_anchors=factor_anchors,
        builds=builds,
        meets=meets,
        demands=demands,
    )
    stage_ref = _stage_payloads(
        cursor,
        family_ref="binding_candidates",
        lane_ref="binding",
        payloads=payloads,
    )
    statements = _publish_binding_stage(cursor, stage_ref=stage_ref)
    if validate_indexed_query and candidate_sets:
        _validate_binding_stage(cursor, stage_ref=stage_ref)
        statements += 1
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=statements)


def persist_streamed_candidate_builds_work_conserving(
    cursor: Any, rows: Sequence[Mapping[str, Any]]
) -> None:
    payloads: list[StagePayload] = []
    for row in rows:
        identity = {
            "generator_build_ref": row["generator_build_ref"],
            "reference_factor_revision_ref": row["reference_factor_revision_ref"],
            "document_pnf_index_ref": row.get("document_pnf_index_ref"),
            "accessibility_declaration_ref": row["accessibility_declaration_ref"],
            "compatibility_declaration_ref": row["compatibility_declaration_ref"],
            "referential_type_ref": row["referential_type_ref"],
        }
        payloads.append(
            StagePayload(
                "candidate_build",
                texts=(
                    str(row["generator_build_ref"]),
                    str(row["candidate_set_ref"]),
                    str(row["reference_factor_revision_ref"]),
                    str(row.get("document_pnf_index_ref") or ""),
                    str(row["accessibility_declaration_ref"]),
                    str(row["compatibility_declaration_ref"]),
                    str(row["referential_type_ref"]),
                    _text_sha(identity),
                    "completed",
                ),
            )
        )
    stage_ref = _stage_payloads(
        cursor,
        family_ref="candidate_builds",
        lane_ref="binding",
        payloads=payloads,
    )
    cursor.execute(
        """
        INSERT INTO execution.binding_candidate_set_build
            (generator_build_ref, candidate_set_ref,
             reference_factor_revision_ref, document_pnf_index_ref,
             accessibility_declaration_ref, compatibility_declaration_ref,
             referential_type_ref, build_key_sha256, build_state_ref)
        SELECT text_01, text_02, text_03, text_04, text_05, text_06,
               text_07, text_08, text_09
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'candidate_build'
        ON CONFLICT (generator_build_ref) DO UPDATE SET
            candidate_set_ref = EXCLUDED.candidate_set_ref,
            reference_factor_revision_ref = EXCLUDED.reference_factor_revision_ref,
            document_pnf_index_ref = EXCLUDED.document_pnf_index_ref,
            accessibility_declaration_ref = EXCLUDED.accessibility_declaration_ref,
            compatibility_declaration_ref = EXCLUDED.compatibility_declaration_ref,
            referential_type_ref = EXCLUDED.referential_type_ref,
            build_key_sha256 = EXCLUDED.build_key_sha256
        """,
        (stage_ref,),
    )
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=1)


def persist_streamed_candidate_links_work_conserving(
    cursor: Any, *, kind: str, rows: Sequence[Mapping[str, Any]]
) -> None:
    specifications = {
        "refinement": (
            "refinement_ref",
            "refinement_candidate_set",
            "resolution.refinement_candidate_set",
        ),
        "meet": (
            "meet_ref",
            "meet_candidate_set",
            "resolution.meet_candidate_set",
        ),
        "demand": (
            "demand_ref",
            "demand_candidate_set",
            "resolution.demand_candidate_set",
        ),
    }
    source_column, row_kind, table = specifications[kind]
    payloads = [
        StagePayload(
            row_kind,
            texts=(str(row[source_column]), str(candidate_set_ref)),
        )
        for row in rows
        for candidate_set_ref in row.get("candidate_set_refs") or ()
    ]
    stage_ref = _stage_payloads(
        cursor,
        family_ref=f"{kind}_candidate_links",
        lane_ref="binding",
        payloads=payloads,
    )
    cursor.execute(
        f"INSERT INTO {table} ({source_column}, candidate_set_ref) "
        "SELECT text_01, text_02 "
        "FROM execution.document_persistence_stage "
        "WHERE stage_ref = %s AND row_kind_ref = %s "
        "ON CONFLICT DO NOTHING",
        (stage_ref, row_kind),
    )
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=1)


__all__ = [
    "persist_binding_candidate_sets_work_conserving",
    "persist_streamed_candidate_builds_work_conserving",
    "persist_streamed_candidate_links_work_conserving",
]
