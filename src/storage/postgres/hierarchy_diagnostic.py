"""Read-only diagnostics for authored sentence-to-paragraph hierarchy."""

from __future__ import annotations

from typing import Any, Mapping

from src.storage.postgres.spacy_parser_model import connect


CONTRACT = "sensiblaw.authored-hierarchy-diagnostic.v0_1"
INTEGRITY_CONTRACT = "sensiblaw.authored-hierarchy-integrity.v0_1"
SENTENCE_KIND = 1
PARAGRAPH_KIND = 3


def classify_hierarchy_diagnostic(observation: Mapping[str, Any]) -> str:
    """Classify observed hierarchy state without inferring or repairing rows."""

    strict = int(observation.get("strict_v2_sentence_count", 0))
    legacy = int(observation.get("non_strict_sentence_count", 0))
    regions = int(observation.get("sentence_region_count", 0))
    mappings = int(observation.get("sentence_region_mapping_count", 0))
    paragraphs = int(observation.get("paragraph_region_count", 0))
    parented = int(observation.get("sentences_parented_to_paragraph", 0))
    identity = bool(observation.get("run_document_identity_consistent", False))

    if not identity:
        return "incompatible_generation_or_revision"
    if strict == 0:
        if legacy:
            return "incompatible_generation_or_revision"
        return "producer_never_run"
    if paragraphs == 0:
        return "producer_never_run"
    if regions == 0 or mappings == 0:
        return "producer/mapping_defect"
    if parented == 0:
        return "wrong_authoritative_relation"
    if mappings != strict or regions != strict or parented != strict:
        return "producer/mapping_defect"
    return "valid_authored_hierarchy"


class HierarchyIntegrityError(RuntimeError):
    """A completed strict-v2 run lacks authoritative sentence hierarchy."""

    def __init__(self, report: Mapping[str, Any]) -> None:
        self.report = dict(report)
        super().__init__(
            "strict-v2 hierarchy integrity failed: "
            f"closed={report.get('closed_strict_v2_sentence_count', 0)}, "
            f"bad_mappings={report.get('closed_sentences_without_exactly_one_region', 0)}, "
            f"bad_parents={report.get('closed_sentences_without_exactly_one_paragraph_parent', 0)}"
        )


def evaluate_hierarchy_integrity(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate the closed strict-v2 hierarchy invariant without database I/O."""

    closed = int(observation.get("closed_strict_v2_sentence_count", 0))
    bad_mappings = int(
        observation.get("closed_sentences_without_exactly_one_region", 0)
    )
    bad_parents = int(
        observation.get("closed_sentences_without_exactly_one_paragraph_parent", 0)
    )
    strict = int(observation.get("strict_v2_sentence_count", 0))
    report = {
        "contract": INTEGRITY_CONTRACT,
        "strict_v2_sentence_count": strict,
        "closed_strict_v2_sentence_count": closed,
        "closed_sentences_without_exactly_one_region": bad_mappings,
        "closed_sentences_without_exactly_one_paragraph_parent": bad_parents,
        "hierarchy_integrity_failure": bool(bad_mappings or bad_parents),
        "database_mutations_performed": False,
        "provider_io_performed": False,
    }
    return report


def assert_hierarchy_integrity(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, Any]:
    """Read and enforce exact mapping/parent counts for closed strict-v2 rows."""

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    WITH sentence_state AS (
                        SELECT sentence.sentence_id,
                               count(mapping.region_id) AS mapping_count,
                               count(region.region_id) FILTER (
                                   WHERE region.closure_state = 3
                               ) AS closed_region_count,
                               count(parent.region_id) FILTER (
                                   WHERE parent.region_kind = 3
                               ) AS paragraph_parent_count
                          FROM execution.semantic_parser_sentence AS sentence
                          LEFT JOIN execution.semantic_pnf_sentence_region AS mapping
                            ON mapping.sentence_id = sentence.sentence_id
                          LEFT JOIN execution.semantic_pnf_region AS region
                            ON region.region_id = mapping.region_id
                          LEFT JOIN execution.semantic_pnf_region AS parent
                            ON parent.region_id = region.parent_region_id
                         WHERE sentence.run_ref = %s
                           AND sentence.document_ref = %s
                           AND sentence.representation_version = 2
                         GROUP BY sentence.sentence_id
                    )
                    SELECT
                        (SELECT count(*) FROM sentence_state),
                        (SELECT count(*) FROM sentence_state
                          WHERE closed_region_count = 1),
                        (SELECT count(*) FROM sentence_state
                          WHERE closed_region_count = 1
                            AND mapping_count <> 1),
                        (SELECT count(*) FROM sentence_state
                          WHERE closed_region_count = 1
                            AND paragraph_parent_count <> 1)
                    """,
                    (run_ref, document_ref),
                )
                row = cursor.fetchone()
                observation = {
                    "strict_v2_sentence_count": int(row[0]),
                    "closed_strict_v2_sentence_count": int(row[1]),
                    "closed_sentences_without_exactly_one_region": int(row[2]),
                    "closed_sentences_without_exactly_one_paragraph_parent": int(
                        row[3]
                    ),
                }
                report = evaluate_hierarchy_integrity(observation)
                report.update(
                    {"run_ref": run_ref, "document_ref": document_ref}
                )
                if report["hierarchy_integrity_failure"]:
                    raise HierarchyIntegrityError(report)
                return report
    finally:
        connection.close()


def _fetchone(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return tuple(row) if row is not None else ()


def _fetchall(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[tuple[Any, ...], ...]:
    cursor.execute(query, params)
    return tuple(tuple(row) for row in cursor.fetchall())


def diagnose_authored_hierarchy(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str | None = None,
) -> dict[str, Any]:
    """Return a fail-closed hierarchy receipt using one read-only transaction."""

    if not run_ref:
        raise ValueError("run_ref is required")
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                run_row = _fetchone(
                    cursor,
                    """
                    SELECT document_ref, authority_backend, lifecycle, sealed,
                           owner_revision, operation_contract_ref, kernel_contract
                      FROM execution.semantic_run
                     WHERE run_ref = %s
                    """,
                    (run_ref,),
                )
                if not run_row:
                    return _empty_receipt(run_ref, document_ref, "no_usable_existing_fixture")
                run_document = str(run_row[0])
                selected_document = document_ref or run_document
                scope = (run_ref, selected_document)

                sentence_counts = _fetchone(
                    cursor,
                    """
                    SELECT count(*) FILTER (WHERE representation_version = 2),
                           count(*) FILTER (WHERE representation_version <> 2),
                           count(*)
                      FROM execution.semantic_parser_sentence
                     WHERE run_ref = %s AND document_ref = %s
                    """,
                    scope,
                )
                region_counts = _fetchone(
                    cursor,
                    """
                    SELECT count(*) FILTER (WHERE region_kind = 1),
                           count(*) FILTER (WHERE region_kind = 3),
                           count(*) FILTER (WHERE region_kind = 1 AND parent_region_id IS NULL),
                           count(*) FILTER (
                               WHERE region_kind = 1 AND parent_region_id IS NOT NULL
                                 AND NOT EXISTS (
                                     SELECT 1 FROM execution.semantic_pnf_region AS parent
                                      WHERE parent.region_id = semantic_pnf_region.parent_region_id
                                        AND parent.region_kind = 3
                                 )
                           )
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s AND document_ref = %s
                    """,
                    scope,
                )
                mapping_counts = _fetchone(
                    cursor,
                    """
                    SELECT count(*), count(DISTINCT mapping.sentence_id),
                           count(DISTINCT mapping.region_id),
                           count(*) FILTER (WHERE region.parent_region_id IS NOT NULL
                                             AND parent.region_kind = 3)
                      FROM execution.semantic_pnf_sentence_region AS mapping
                      JOIN execution.semantic_parser_sentence AS sentence
                        ON sentence.sentence_id = mapping.sentence_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = mapping.region_id
                      LEFT JOIN execution.semantic_pnf_region AS parent
                        ON parent.region_id = region.parent_region_id
                     WHERE sentence.run_ref = %s AND sentence.document_ref = %s
                       AND sentence.representation_version = 2
                    """,
                    scope,
                )
                child_rows = _fetchall(
                    cursor,
                    """
                    SELECT parent.region_id, count(child.region_id)
                      FROM execution.semantic_pnf_region AS parent
                      LEFT JOIN execution.semantic_pnf_region AS child
                        ON child.parent_region_id = parent.region_id
                       AND child.region_kind = 1
                     WHERE parent.run_ref = %s AND parent.document_ref = %s
                       AND parent.region_kind = 3
                     GROUP BY parent.region_id
                     ORDER BY parent.region_id
                    """,
                    scope,
                )
                work_rows = _fetchall(
                    cursor,
                    """
                    SELECT state.state_name, count(*)
                      FROM execution.semantic_pnf_work_item AS work
                      JOIN execution.semantic_pnf_work_state AS state
                        ON state.state_id = work.state_id
                     WHERE work.run_ref = %s AND work.document_ref = %s
                     GROUP BY state.state_name ORDER BY state.state_name
                    """,
                    scope,
                )
                revision_rows = _fetchall(
                    cursor,
                    """
                    SELECT region_kind, count(*), min(graph_revision),
                           max(graph_revision)
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s AND document_ref = %s
                     GROUP BY region_kind ORDER BY region_kind
                    """,
                    scope,
                )
                identity_row = _fetchone(
                    cursor,
                    """
                    SELECT (%s = %s),
                           NOT EXISTS (
                               SELECT 1 FROM execution.semantic_pnf_region
                                WHERE run_ref = %s AND document_ref = %s
                                  AND (run_ref <> %s OR document_ref <> %s)
                           ),
                           NOT EXISTS (
                               SELECT 1 FROM execution.semantic_parser_sentence
                                WHERE run_ref = %s AND document_ref = %s
                                  AND (run_ref <> %s OR document_ref <> %s)
                           )
                    """,
                    (run_document, selected_document, *scope, *scope, *scope, *scope),
                )

                receipt = {
                    "contract": CONTRACT,
                    "run_ref": run_ref,
                    "document_ref": selected_document,
                    "run": {
                        "document_ref": run_document,
                        "authority_backend": run_row[1],
                        "lifecycle": run_row[2],
                        "sealed": bool(run_row[3]),
                        "owner_revision": int(run_row[4]),
                        "operation_contract_ref": run_row[5],
                        "kernel_contract": run_row[6],
                    },
                    "strict_v2_sentence_count": int(sentence_counts[0]),
                    "non_strict_sentence_count": int(sentence_counts[1]),
                    "sentence_region_mapping_count": int(mapping_counts[0]),
                    "sentence_region_count": int(region_counts[0]),
                    "paragraph_region_count": int(region_counts[1]),
                    "sentences_parented_to_paragraph": int(mapping_counts[3]),
                    "orphan_sentence_regions": int(region_counts[2]),
                    "sentence_regions_without_paragraph_parent": int(region_counts[3]),
                    "paragraph_child_counts": [
                        {"region_id": int(region_id), "sentence_children": int(count)}
                        for region_id, count in child_rows
                    ],
                    "work_item_states": {str(name): int(count) for name, count in work_rows},
                    "region_graph_revisions": {
                        str(kind): {
                            "region_count": int(count),
                            "min": int(minimum),
                            "max": int(maximum),
                        }
                        for kind, count, minimum, maximum in revision_rows
                    },
                    "run_document_identity_consistent": bool(identity_row and all(identity_row)),
                    "database_mutations_performed": False,
                    "provider_io_performed": False,
                }
                receipt["classification"] = classify_hierarchy_diagnostic(receipt)
                return receipt
    finally:
        connection.close()


def _empty_receipt(
    run_ref: str, document_ref: str | None, classification: str
) -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "classification": classification,
        "strict_v2_sentence_count": 0,
        "non_strict_sentence_count": 0,
        "sentence_region_mapping_count": 0,
        "sentence_region_count": 0,
        "paragraph_region_count": 0,
        "sentences_parented_to_paragraph": 0,
        "orphan_sentence_regions": 0,
        "sentence_regions_without_paragraph_parent": 0,
        "paragraph_child_counts": [],
        "work_item_states": {},
        "region_graph_revisions": {},
        "run_document_identity_consistent": False,
        "database_mutations_performed": False,
        "provider_io_performed": False,
    }


def search_existing_authored_hierarchies(
    database_url: str, *, limit: int = 20
) -> tuple[dict[str, Any], ...]:
    """Find existing complete strict-v2 authored memberships, read-only."""

    if limit <= 0:
        raise ValueError("limit must be positive")
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                rows = _fetchall(
                    cursor,
                    """
                    SELECT sentence.run_ref, sentence.document_ref,
                           count(*) AS strict_sentences,
                           count(mapping.region_id) AS mappings,
                           count(*) FILTER (WHERE parent.region_kind = 3) AS parented
                      FROM execution.semantic_parser_sentence AS sentence
                      LEFT JOIN execution.semantic_pnf_sentence_region AS mapping
                        ON mapping.sentence_id = sentence.sentence_id
                      LEFT JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = mapping.region_id
                      LEFT JOIN execution.semantic_pnf_region AS parent
                        ON parent.region_id = region.parent_region_id
                     WHERE sentence.representation_version = 2
                     GROUP BY sentence.run_ref, sentence.document_ref
                    HAVING count(*) = count(mapping.region_id)
                       AND count(*) = count(*) FILTER (WHERE parent.region_kind = 3)
                     ORDER BY sentence.run_ref, sentence.document_ref
                     LIMIT %s
                    """,
                    (limit,),
                )
                return tuple(
                    {
                        "run_ref": str(run_ref),
                        "document_ref": str(document_ref),
                        "strict_v2_sentence_count": int(strict),
                        "sentence_region_mapping_count": int(mappings),
                        "sentences_parented_to_paragraph": int(parented),
                        "classification": "valid_authored_hierarchy",
                    }
                    for run_ref, document_ref, strict, mappings, parented in rows
                )
    finally:
        connection.close()


__all__ = [
    "CONTRACT",
    "HierarchyIntegrityError",
    "INTEGRITY_CONTRACT",
    "assert_hierarchy_integrity",
    "classify_hierarchy_diagnostic",
    "diagnose_authored_hierarchy",
    "evaluate_hierarchy_integrity",
    "search_existing_authored_hierarchies",
]
