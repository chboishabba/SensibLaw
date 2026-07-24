"""Batch-oriented persistence for set-valued PNF binding candidates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.storage.postgres.binding_candidate_store import (
    _sha,
    _validate_indexed_membership,
)


def persist_binding_candidate_sets_batched(
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
    anchor_rows = []
    morphology_rows = []
    for row in factor_anchors:
        revision_ref = factor_revisions.get(str(row["factor_ref"]))
        if revision_ref is None:
            continue
        anchor_rows.append(
            (
                revision_ref,
                str(row["document_ref"]),
                row.get("sentence_index"),
                row.get("clause_ref"),
                int(row["start_token"]),
                int(row["end_token"]),
                str(row["pnf_kind_ref"]),
                str(row.get("morphology_sha256") or ""),
                row.get("discourse_unit_ref"),
                row.get("paragraph_index"),
                row.get("quotation_depth"),
                row.get("reporting_scope_ref"),
                row.get("coordination_group_ref"),
                row.get("parser_pos"),
                row.get("parser_dependency"),
            )
        )
        morphology_rows.extend(
            (revision_ref, str(feature_ref), str(value_ref))
            for feature_ref, values in sorted((row.get("morphology") or {}).items())
            for value_ref in sorted(str(value) for value in values)
        )
    if anchor_rows:
        cursor.executemany(
            """
            INSERT INTO pnf.factor_anchor
                (factor_revision_ref, document_ref, sentence_index, clause_ref,
                 start_token, end_token, pnf_kind_ref, morphology_sha256,
                 discourse_unit_ref, paragraph_index, quotation_depth,
                 reporting_scope_ref, coordination_group_ref, parser_pos_ref,
                 parser_dependency_ref)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s)
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
            anchor_rows,
        )
    if morphology_rows:
        cursor.executemany(
            """
            INSERT INTO pnf.factor_morphology
                (factor_revision_ref, feature_ref, value_ref)
            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """,
            morphology_rows,
        )

    builds_by_set = {str(row["candidate_set_ref"]): dict(row) for row in builds}
    set_rows = []
    build_rows = []
    assessment_rows = []
    member_rows = []
    exclusion_rows = []
    persisted_reference_revisions: dict[str, str] = {}
    for row in sorted(candidate_sets, key=lambda value: str(value["candidate_set_ref"])):
        candidate_set_ref = str(row["candidate_set_ref"])
        reference_factor_ref = str(row["reference_factor_ref"])
        reference_revision = factor_revisions.get(reference_factor_ref)
        if reference_revision is None:
            raise ValueError(
                "binding candidate set references an unpersisted factor revision"
            )
        persisted_reference_revisions[candidate_set_ref] = reference_revision
        set_rows.append(
            (
                candidate_set_ref,
                str(row["document_ref"]),
                reference_factor_ref,
                reference_revision,
                str(row["referential_type_ref"]),
                str(row["accessibility_declaration_ref"]),
                str(row["compatibility_declaration_ref"]),
                str(row["generator_build_ref"]),
                str(row["compatibility_state"]),
                int(row["member_count"]),
                _sha(row),
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
        build_rows.append(
            (
                str(build["generator_build_ref"]),
                candidate_set_ref,
                reference_revision,
                str(build.get("document_pnf_index_ref") or ""),
                str(build["accessibility_declaration_ref"]),
                str(build["compatibility_declaration_ref"]),
                str(build["referential_type_ref"]),
                _sha(build_identity),
            )
        )
        for ordinal, member in enumerate(row.get("members") or ()):
            assessment_ref = str(member["compatibility_assessment_ref"])
            candidate_factor_ref = str(member["candidate_factor_ref"])
            accessibility_path_ref = str(member["accessibility_path_ref"])
            assessment_rows.append(
                (
                    assessment_ref,
                    candidate_set_ref,
                    candidate_factor_ref,
                    str(member["compatibility_state"]),
                    accessibility_path_ref,
                    _sha(member),
                )
            )
            member_rows.append(
                (
                    candidate_set_ref,
                    candidate_factor_ref,
                    assessment_ref,
                    accessibility_path_ref,
                    ordinal,
                )
            )
        exclusion_rows.extend(
            (
                candidate_set_ref,
                str(summary["reason_ref"]),
                int(summary["excluded_count"]),
                str(summary["generator_build_ref"]),
            )
            for summary in row.get("exclusion_summaries") or ()
        )
    if set_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.binding_candidate_set
                (candidate_set_ref, document_ref, reference_factor_ref,
                 reference_factor_revision_ref, referential_type_ref,
                 accessibility_declaration_ref, compatibility_declaration_ref,
                 generator_build_ref, compatibility_state_ref, member_count,
                 candidate_set_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (candidate_set_ref) DO NOTHING
            """,
            set_rows,
        )
        cursor.executemany(
            """
            INSERT INTO execution.binding_candidate_set_build
                (generator_build_ref, candidate_set_ref,
                 reference_factor_revision_ref, document_pnf_index_ref,
                 accessibility_declaration_ref, compatibility_declaration_ref,
                 referential_type_ref, build_key_sha256, build_state_ref)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'completed')
            ON CONFLICT (generator_build_ref) DO NOTHING
            """,
            build_rows,
        )
    if assessment_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.binding_compatibility_assessment
                (compatibility_assessment_ref, candidate_set_ref,
                 candidate_factor_ref, compatibility_state_ref,
                 accessibility_path_ref, assessment_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (compatibility_assessment_ref) DO NOTHING
            """,
            assessment_rows,
        )
        cursor.executemany(
            """
            INSERT INTO resolution.binding_candidate_member
                (candidate_set_ref, candidate_factor_ref,
                 compatibility_assessment_ref, accessibility_path_ref, ordinal)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (candidate_set_ref, candidate_factor_ref) DO NOTHING
            """,
            member_rows,
        )
    if exclusion_rows:
        cursor.executemany(
            """
            INSERT INTO resolution.binding_exclusion_summary
                (candidate_set_ref, reason_ref, excluded_count, generator_build_ref)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (candidate_set_ref, reason_ref) DO UPDATE SET
                excluded_count = EXCLUDED.excluded_count,
                generator_build_ref = EXCLUDED.generator_build_ref
            """,
            exclusion_rows,
        )

    known_sets = {str(row["candidate_set_ref"]) for row in candidate_sets}
    refinement_links = [
        (str(refinement["refinement_ref"]), str(candidate_set_ref))
        for refinement in refinements
        for candidate_set_ref in refinement.get("candidate_set_refs") or ()
        if str(candidate_set_ref) in known_sets
    ]
    meet_links = [
        (str(meet["meet_ref"]), str(candidate_set_ref))
        for meet in meets
        for candidate_set_ref in meet.get("candidate_set_refs") or ()
        if str(candidate_set_ref) in known_sets
    ]
    demand_links = [
        (str(demand["demand_ref"]), str(candidate_set_ref))
        for demand in demands
        for candidate_set_ref in demand.get("candidate_set_refs") or ()
        if str(candidate_set_ref) in known_sets
    ]
    for statement, rows in (
        (
            "INSERT INTO resolution.refinement_candidate_set "
            "(refinement_ref, candidate_set_ref) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            refinement_links,
        ),
        (
            "INSERT INTO resolution.meet_candidate_set "
            "(meet_ref, candidate_set_ref) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            meet_links,
        ),
        (
            "INSERT INTO resolution.demand_candidate_set "
            "(demand_ref, candidate_set_ref) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            demand_links,
        ),
    ):
        if rows:
            cursor.executemany(statement, rows)

    if validate_indexed_query:
        for candidate_set in candidate_sets:
            candidate_set_ref = str(candidate_set["candidate_set_ref"])
            _validate_indexed_membership(
                cursor,
                candidate_set=candidate_set,
                reference_factor_revision_ref=persisted_reference_revisions[
                    candidate_set_ref
                ],
            )


__all__ = ["persist_binding_candidate_sets_batched"]
