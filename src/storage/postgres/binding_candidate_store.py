"""Normalized persistence for set-valued PNF binding candidates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


def _sha(value: object) -> str:
    return canonical_sha256(value)


def persist_binding_candidate_sets(
    cursor: Any,
    *,
    candidate_sets: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
) -> None:
    """Persist candidate sets, members, exclusions, and refinement links.

    Pairwise binding evidence is intentionally not persisted here.  The set and
    member rows reconstruct the same branch-preserving candidate membership.
    """

    for row in candidate_sets:
        candidate_set_ref = str(row["candidate_set_ref"])
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
                str(row["reference_factor_ref"]),
                str(row["reference_factor_revision_ref"]),
                str(row["referential_type_ref"]),
                str(row["accessibility_declaration_ref"]),
                str(row["compatibility_declaration_ref"]),
                str(row["generator_build_ref"]),
                str(row["compatibility_state"]),
                int(row["member_count"]),
                _sha(row),
            ),
        )
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

    known_sets = {
        str(row["candidate_set_ref"]) for row in candidate_sets
    }
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


__all__ = ["persist_binding_candidate_sets"]
