"""Normalized persistence for set-valued PNF binding candidates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


def _sha(value: object) -> str:
    return canonical_sha256(value)


def _persist_factor_anchors(
    cursor: Any,
    *,
    factor_anchors: Sequence[Mapping[str, Any]],
    factor_revisions: Mapping[str, str],
) -> None:
    for row in factor_anchors:
        factor_ref = str(row["factor_ref"])
        factor_revision_ref = factor_revisions.get(factor_ref)
        if factor_revision_ref is None:
            continue
        cursor.execute(
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
            (
                factor_revision_ref,
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
            ),
        )
        for feature_ref, values in sorted((row.get("morphology") or {}).items()):
            for value_ref in sorted(str(value) for value in values):
                cursor.execute(
                    """
                    INSERT INTO pnf.factor_morphology
                        (factor_revision_ref, feature_ref, value_ref)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (factor_revision_ref, str(feature_ref), value_ref),
                )


def _persist_build(cursor: Any, row: Mapping[str, Any]) -> None:
    build_identity = {
        "generator_build_ref": row["generator_build_ref"],
        "reference_factor_revision_ref": row["reference_factor_revision_ref"],
        "document_pnf_index_ref": row.get("document_pnf_index_ref"),
        "accessibility_declaration_ref": row["accessibility_declaration_ref"],
        "compatibility_declaration_ref": row["compatibility_declaration_ref"],
        "referential_type_ref": row["referential_type_ref"],
    }
    cursor.execute(
        """
        INSERT INTO execution.binding_candidate_set_build
            (generator_build_ref, candidate_set_ref,
             reference_factor_revision_ref, document_pnf_index_ref,
             accessibility_declaration_ref, compatibility_declaration_ref,
             referential_type_ref, build_key_sha256, build_state_ref)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'completed')
        ON CONFLICT (generator_build_ref) DO NOTHING
        """,
        (
            str(row["generator_build_ref"]),
            str(row["candidate_set_ref"]),
            str(row["reference_factor_revision_ref"]),
            str(row.get("document_pnf_index_ref") or ""),
            str(row["accessibility_declaration_ref"]),
            str(row["compatibility_declaration_ref"]),
            str(row["referential_type_ref"]),
            _sha(build_identity),
        ),
    )


def _validate_indexed_membership(
    cursor: Any,
    *,
    candidate_set: Mapping[str, Any],
    reference_factor_revision_ref: str,
) -> None:
    cursor.execute(
        """
        SELECT candidate_factor_ref
        FROM resolution.query_binding_candidates(%s, %s, %s, %s, 64)
        """,
        (
            reference_factor_revision_ref,
            str(candidate_set["referential_type_ref"]),
            str(candidate_set["accessibility_declaration_ref"]),
            str(candidate_set["compatibility_declaration_ref"]),
        ),
    )
    actual = {str(row[0]) for row in cursor.fetchall()}
    expected = {
        str(row["candidate_factor_ref"])
        for row in candidate_set.get("members") or ()
    }
    if actual != expected:
        raise ValueError(
            "PostgreSQL structural binding index disagrees with candidate-set membership: "
            f"expected={sorted(expected)!r} actual={sorted(actual)!r}"
        )


def persist_binding_candidate_sets(
    cursor: Any,
    *,
    candidate_sets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
    factor_revisions: Mapping[str, str],
    factor_anchors: Sequence[Mapping[str, Any]] = (),
    builds: Sequence[Mapping[str, Any]] = (),
    meets: Sequence[Mapping[str, Any]] = (),
    validate_indexed_query: bool = False,
) -> None:
    """Persist candidate sets, indexes, members, exclusions, and links.

    ``factor_revisions`` must describe the pre-binding graph revisions used by
    candidate-set build identities. Resulting factor revisions are persisted by
    the caller through the ordinary immutable refinement path.
    """

    _persist_factor_anchors(
        cursor,
        factor_anchors=factor_anchors,
        factor_revisions=factor_revisions,
    )
    builds_by_set = {
        str(row["candidate_set_ref"]): row for row in builds
    }
    persisted_reference_revisions: dict[str, str] = {}
    for row in candidate_sets:
        candidate_set_ref = str(row["candidate_set_ref"])
        reference_factor_ref = str(row["reference_factor_ref"])
        reference_factor_revision_ref = factor_revisions.get(reference_factor_ref)
        if reference_factor_revision_ref is None:
            raise ValueError(
                "binding candidate set references an unpersisted factor revision"
            )
        persisted_reference_revisions[candidate_set_ref] = (
            reference_factor_revision_ref
        )
        cursor.execute(
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
            (
                candidate_set_ref,
                str(row["document_ref"]),
                reference_factor_ref,
                reference_factor_revision_ref,
                str(row["referential_type_ref"]),
                str(row["accessibility_declaration_ref"]),
                str(row["compatibility_declaration_ref"]),
                str(row["generator_build_ref"]),
                str(row["compatibility_state"]),
                int(row["member_count"]),
                _sha(row),
            ),
        )
        build = builds_by_set.get(candidate_set_ref)
        if build is None:
            build = {
                "generator_build_ref": row["generator_build_ref"],
                "candidate_set_ref": candidate_set_ref,
                "reference_factor_revision_ref": reference_factor_revision_ref,
                "document_pnf_index_ref": "",
                "accessibility_declaration_ref": row[
                    "accessibility_declaration_ref"
                ],
                "compatibility_declaration_ref": row[
                    "compatibility_declaration_ref"
                ],
                "referential_type_ref": row["referential_type_ref"],
            }
        else:
            build = {
                **build,
                "reference_factor_revision_ref": reference_factor_revision_ref,
            }
        _persist_build(cursor, build)
        for ordinal, member in enumerate(row.get("members") or ()):
            assessment_ref = str(member["compatibility_assessment_ref"])
            candidate_factor_ref = str(member["candidate_factor_ref"])
            accessibility_path_ref = str(member["accessibility_path_ref"])
            cursor.execute(
                """
                INSERT INTO resolution.binding_compatibility_assessment
                    (compatibility_assessment_ref, candidate_set_ref,
                     candidate_factor_ref, compatibility_state_ref,
                     accessibility_path_ref, assessment_sha256)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (compatibility_assessment_ref) DO NOTHING
                """,
                (
                    assessment_ref,
                    candidate_set_ref,
                    candidate_factor_ref,
                    str(member["compatibility_state"]),
                    accessibility_path_ref,
                    _sha(member),
                ),
            )
            cursor.execute(
                """
                INSERT INTO resolution.binding_candidate_member
                    (candidate_set_ref, candidate_factor_ref,
                     compatibility_assessment_ref, accessibility_path_ref,
                     ordinal)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (candidate_set_ref, candidate_factor_ref) DO NOTHING
                """,
                (
                    candidate_set_ref,
                    candidate_factor_ref,
                    assessment_ref,
                    accessibility_path_ref,
                    ordinal,
                ),
            )
        for summary in row.get("exclusion_summaries") or ():
            cursor.execute(
                """
                INSERT INTO resolution.binding_exclusion_summary
                    (candidate_set_ref, reason_ref, excluded_count,
                     generator_build_ref)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (candidate_set_ref, reason_ref) DO UPDATE SET
                    excluded_count = EXCLUDED.excluded_count,
                    generator_build_ref = EXCLUDED.generator_build_ref
                """,
                (
                    candidate_set_ref,
                    str(summary["reason_ref"]),
                    int(summary["excluded_count"]),
                    str(summary["generator_build_ref"]),
                ),
            )

    known_sets = {str(row["candidate_set_ref"]) for row in candidate_sets}
    for refinement in refinements:
        for candidate_set_ref in refinement.get("candidate_set_refs") or ():
            candidate_set_ref = str(candidate_set_ref)
            if candidate_set_ref not in known_sets:
                continue
            cursor.execute(
                """
                INSERT INTO resolution.refinement_candidate_set
                    (refinement_ref, candidate_set_ref)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (str(refinement["refinement_ref"]), candidate_set_ref),
            )
    for meet in meets:
        for candidate_set_ref in meet.get("candidate_set_refs") or ():
            candidate_set_ref = str(candidate_set_ref)
            if candidate_set_ref not in known_sets:
                continue
            cursor.execute(
                """
                INSERT INTO resolution.meet_candidate_set
                    (meet_ref, candidate_set_ref)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (str(meet["meet_ref"]), candidate_set_ref),
            )
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


__all__ = ["persist_binding_candidate_sets"]
