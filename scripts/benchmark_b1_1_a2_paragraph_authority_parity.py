#!/usr/bin/env python3
"""Read-only B1.1 scoped A2 -> paragraph-boundary authority parity.

This benchmark is deliberately narrower than whole paragraph-frontier equality.
It compares only the four A2 operator families already certified at sentence
level (normative, condition, exception, transition) against the transported
paragraph boundary authority introduced by C2/C3.

The formal distinction is preserved:

    emitted sentence delta
      -> sentence->paragraph natural transport / associative fusion
      -> boundary admission
      -> transported paragraph boundary authority

Factors and unresolved residual demands are compared directly. Objects are
compared only after applying the same promotion predicate used by sentence
interface admission; unpromoted local objects are not falsely required to
appear at the parent boundary. Later parent-local promotion, actor summaries,
demand resolution, and root lookup are outside this B1.1 projection.

A bounded sentence sample is admitted only when it contains every sentence
child of each selected paragraph.  Partial paragraphs fail closed rather than
making valid authority rows appear as false-positive extras.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_fibre_local_numeric_layout import _load_sentences
from scripts.benchmark_packed_normative_parity import _load_operator_lexicon
from scripts.benchmark_sentence_paragraph_delta_transport import _load_paragraph_membership
from src.pnf.fibre_local_numeric import pack_sentence_fibre
from src.pnf.fibre_local_relational_bridge import localize_relational_sentence
from src.pnf.numeric_hyperfabric import should_promote
from src.pnf.packed_operator_family_admission import (
    FAMILY_NAMES,
    build_operator_family_admission_plan,
    compose_sparse_packed_operator_families,
)
from src.pnf.sentence_paragraph_delta_transport import (
    ParagraphSemanticDelta,
    fuse_paragraph_deltas,
    paragraph_interface_keys,
    sentence_semantic_delta_from_operator_families,
    transport_sentence_delta_to_paragraph,
)
from src.storage.postgres import numeric_hyperfabric_store as store
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.b1-1-a2-paragraph-authority-parity.v0_2"
A2_FACTOR_TYPE_NAMES = (
    "semantic.normative_relation",
    "semantic.legal_condition",
    "semantic.legal_exception",
    "semantic.legal_transition",
)


def _load_profile(database_url: str) -> Any:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                return store._load_profile(cursor)
    finally:
        connection.close()


def _assert_complete_paragraph_selection(
    database_url: str,
    *,
    paragraph_ids: Iterable[int],
    sentence_refs: Iterable[str],
) -> dict[str, int]:
    parents = tuple(sorted({int(value) for value in paragraph_ids}))
    refs = tuple(sorted({str(value) for value in sentence_refs}))
    if not parents:
        return {"paragraph_count": 0, "sentence_child_count": 0}
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT parent.region_id,
                           count(DISTINCT child.region_id) AS total_children,
                           count(DISTINCT child.region_id) FILTER (
                               WHERE sentence.sentence_ref = ANY(%s)
                           ) AS selected_children
                      FROM execution.semantic_pnf_region AS parent
                      JOIN execution.semantic_pnf_region AS child
                        ON child.parent_region_id = parent.region_id
                       AND child.region_kind = 1
                      LEFT JOIN execution.semantic_pnf_sentence_region AS mapping
                        ON mapping.region_id = child.region_id
                      LEFT JOIN execution.semantic_parser_sentence AS sentence
                        ON sentence.sentence_id = mapping.sentence_id
                     WHERE parent.region_id = ANY(%s)
                     GROUP BY parent.region_id
                     ORDER BY parent.region_id
                    """,
                    (list(refs), list(parents)),
                )
                rows = tuple(
                    (int(parent_id), int(total), int(selected))
                    for parent_id, total, selected in cursor.fetchall()
                )
    finally:
        connection.close()

    by_parent = {parent_id: (total, selected) for parent_id, total, selected in rows}
    missing_parent_rows = [parent_id for parent_id in parents if parent_id not in by_parent]
    partial = [
        (parent_id, total, selected)
        for parent_id, (total, selected) in sorted(by_parent.items())
        if total != selected
    ]
    if missing_parent_rows or partial:
        raise RuntimeError(
            "B1.1 requires complete sentence coverage for every selected paragraph: "
            f"missing_parents={missing_parent_rows[:20]!r} partial={partial[:20]!r}"
        )
    return {
        "paragraph_count": len(parents),
        "sentence_child_count": sum(total for total, _selected in by_parent.values()),
    }


def _load_scoped_boundary_authority(
    database_url: str,
    *,
    paragraph_ids: Iterable[int],
    factor_type_ids: Iterable[int],
) -> dict[int, dict[str, frozenset[tuple[int, int]]]]:
    parents = tuple(sorted({int(value) for value in paragraph_ids}))
    factor_types = tuple(sorted({int(value) for value in factor_type_ids}))
    authority: dict[int, dict[str, set[tuple[int, int]]]] = {
        parent_id: {"object": set(), "factor": set(), "demand": set()}
        for parent_id in parents
    }
    if not parents:
        return {}
    if not factor_types:
        raise RuntimeError("A2 factor type id set is empty")

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT to_regclass(
                        'execution.semantic_pnf_parent_delta_projection'
                    ) IS NOT NULL
                    """
                )
                if not bool(cursor.fetchone()[0]):
                    raise RuntimeError(
                        "B1.1 requires the transported parent boundary projection"
                    )

                cursor.execute(
                    """
                    SELECT projection.parent_region_id,
                           factor.factor_type_symbol_id,
                           factor.predicate_symbol_id
                      FROM execution.semantic_pnf_parent_delta_projection AS projection
                      JOIN execution.semantic_pnf_factor AS factor
                        ON factor.factor_id = projection.target_id
                     WHERE projection.parent_region_id = ANY(%s)
                       AND projection.target_kind = 2
                       AND factor.factor_type_symbol_id = ANY(%s)
                     GROUP BY projection.parent_region_id,
                              factor.factor_type_symbol_id,
                              factor.predicate_symbol_id
                     ORDER BY projection.parent_region_id,
                              factor.factor_type_symbol_id,
                              factor.predicate_symbol_id
                    """,
                    (list(parents), list(factor_types)),
                )
                for parent_id, factor_type_id, predicate_id in cursor.fetchall():
                    authority[int(parent_id)]["factor"].add(
                        (int(factor_type_id), int(predicate_id))
                    )

                cursor.execute(
                    """
                    SELECT projection.parent_region_id,
                           demand.expected_factor_type_symbol_id,
                           demand.residual_type_symbol_id
                      FROM execution.semantic_pnf_parent_delta_projection AS projection
                      JOIN execution.semantic_pnf_demand AS demand
                        ON demand.demand_id = projection.target_id
                     WHERE projection.parent_region_id = ANY(%s)
                       AND projection.target_kind = 3
                       AND demand.expected_factor_type_symbol_id = ANY(%s)
                       AND demand.residual_type_symbol_id IS NOT NULL
                     GROUP BY projection.parent_region_id,
                              demand.expected_factor_type_symbol_id,
                              demand.residual_type_symbol_id
                     ORDER BY projection.parent_region_id,
                              demand.expected_factor_type_symbol_id,
                              demand.residual_type_symbol_id
                    """,
                    (list(parents), list(factor_types)),
                )
                for parent_id, factor_type_id, residual_type_id in cursor.fetchall():
                    authority[int(parent_id)]["demand"].add(
                        (int(factor_type_id), int(residual_type_id))
                    )

                # An A2 object belongs to this projection only when it is both
                # boundary-admitted and participates in an A2 factor from the
                # same child interface.  This prevents unrelated sentence
                # objects from leaking into the scoped comparison.
                cursor.execute(
                    """
                    SELECT DISTINCT object_projection.parent_region_id,
                           object.object_kind_symbol_id,
                           object.head_symbol_id
                      FROM execution.semantic_pnf_parent_delta_projection
                           AS object_projection
                      JOIN execution.semantic_pnf_object AS object
                        ON object.object_id = object_projection.target_id
                     WHERE object_projection.parent_region_id = ANY(%s)
                       AND object_projection.target_kind = 1
                       AND object.head_symbol_id IS NOT NULL
                       AND EXISTS (
                           SELECT 1
                             FROM execution.semantic_pnf_parent_delta_projection
                                  AS factor_projection
                             JOIN execution.semantic_pnf_factor AS factor
                               ON factor.factor_id = factor_projection.target_id
                             JOIN execution.semantic_pnf_hyperedge AS edge
                               ON edge.factor_id = factor.factor_id
                              AND edge.object_id = object_projection.target_id
                            WHERE factor_projection.parent_region_id
                                  = object_projection.parent_region_id
                              AND factor_projection.child_interface_id
                                  = object_projection.child_interface_id
                              AND factor_projection.target_kind = 2
                              AND factor.factor_type_symbol_id = ANY(%s)
                       )
                     ORDER BY object_projection.parent_region_id,
                              object.object_kind_symbol_id,
                              object.head_symbol_id
                    """,
                    (list(parents), list(factor_types)),
                )
                for parent_id, object_kind_id, head_symbol_id in cursor.fetchall():
                    authority[int(parent_id)]["object"].add(
                        (int(object_kind_id), int(head_symbol_id))
                    )
    finally:
        connection.close()

    return {
        parent_id: {
            family: frozenset(values)
            for family, values in families.items()
        }
        for parent_id, families in authority.items()
    }


def benchmark_b1_1_a2_paragraph_authority_parity(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str | None = None,
    limit_sentences: int = 10_000,
) -> dict[str, Any]:
    if limit_sentences <= 0:
        raise ValueError("limit_sentences must be positive")

    started = monotonic_ns()
    sentences = _load_sentences(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        limit_sentences=limit_sentences,
    )
    lexicon = _load_operator_lexicon(database_url)
    profile = _load_profile(database_url)
    plan = build_operator_family_admission_plan(lexicon)
    membership = _load_paragraph_membership(
        database_url,
        run_ref=run_ref,
        sentence_refs=(sentence.sentence_ref for sentence in sentences),
    )
    load_ns = monotonic_ns() - started

    missing_membership = [
        sentence.sentence_ref
        for sentence in sentences
        if sentence.sentence_ref not in membership
    ]
    if missing_membership:
        raise RuntimeError(
            "B1.1 selected sentences are missing authored paragraph parents: "
            f"count={len(missing_membership)} first={missing_membership[:20]!r}"
        )
    coverage = _assert_complete_paragraph_selection(
        database_url,
        paragraph_ids=(parent_id for parent_id, _ordinal in membership.values()),
        sentence_refs=(sentence.sentence_ref for sentence in sentences),
    )

    paragraph_children: dict[int, list[ParagraphSemanticDelta]] = defaultdict(list)
    admitted_objects: dict[int, set[tuple[int, int]]] = defaultdict(set)
    a2_ns = 0
    transport_ns = 0
    source_interior_rescans = 0
    token_count = 0
    admitted_sentence_count = 0

    for sentence in sentences:
        local = localize_relational_sentence(sentence)
        packed = pack_sentence_fibre(local)
        token_count += packed.token_count
        paragraph_id, child_ordinal = membership[sentence.sentence_ref]

        solve_started = monotonic_ns()
        a2 = compose_sparse_packed_operator_families(packed, lexicon, plan=plan)
        a2_ns += monotonic_ns() - solve_started
        sentence_delta = sentence_semantic_delta_from_operator_families(
            sentence.sentence_ordinal,
            a2,
        )
        if sentence_delta.objects or sentence_delta.factors or sentence_delta.residuals:
            admitted_sentence_count += 1

        # Boundary admission is deliberately distinct from local emission.
        for family in FAMILY_NAMES:
            for obj in a2.deltas[family].objects:
                if should_promote(obj.promotion_evidence, profile):
                    admitted_objects[paragraph_id].add(
                        (int(obj.object_kind_symbol_id), int(obj.head_symbol_id))
                    )

        transport_started = monotonic_ns()
        transported = transport_sentence_delta_to_paragraph(
            sentence_delta,
            child_ordinal=child_ordinal,
        )
        transport_ns += monotonic_ns() - transport_started
        source_interior_rescans += transported.work.source_token_rescan_count
        paragraph_children[paragraph_id].append(transported.delta)

    fusion_started = monotonic_ns()
    expected: dict[int, dict[str, frozenset[tuple[int, int]]]] = {}
    fusion_steps = 0
    for paragraph_id, children in paragraph_children.items():
        current = ParagraphSemanticDelta((), (), (), ())
        for child in children:
            fused = fuse_paragraph_deltas(current, child)
            source_interior_rescans += fused.work.source_token_rescan_count
            fusion_steps += 1
            current = fused.delta
        keys = paragraph_interface_keys(current)
        expected[paragraph_id] = {
            "object": frozenset(admitted_objects[paragraph_id]),
            "factor": keys["factor"],
            "demand": keys["demand"],
        }
    fusion_ns = monotonic_ns() - fusion_started

    factor_type_ids = tuple(
        int(lexicon.factor_type_ids[name]) for name in A2_FACTOR_TYPE_NAMES
    )
    authority_started = monotonic_ns()
    actual = _load_scoped_boundary_authority(
        database_url,
        paragraph_ids=expected,
        factor_type_ids=factor_type_ids,
    )
    authority_ns = monotonic_ns() - authority_started

    mismatch_paragraphs: list[dict[str, Any]] = []
    mismatch_counts = {"object": 0, "factor": 0, "demand": 0}
    missing_counts = {"object": 0, "factor": 0, "demand": 0}
    extra_counts = {"object": 0, "factor": 0, "demand": 0}
    for paragraph_id in sorted(expected):
        expected_families = expected[paragraph_id]
        actual_families = actual.get(
            paragraph_id,
            {"object": frozenset(), "factor": frozenset(), "demand": frozenset()},
        )
        paragraph_mismatch: dict[str, Any] = {"paragraph_region_id": paragraph_id}
        any_mismatch = False
        for family in ("object", "factor", "demand"):
            missing = expected_families[family] - actual_families[family]
            extra = actual_families[family] - expected_families[family]
            if missing or extra:
                any_mismatch = True
                mismatch_counts[family] += 1
                missing_counts[family] += len(missing)
                extra_counts[family] += len(extra)
                paragraph_mismatch[family] = {
                    "missing": [list(value) for value in sorted(missing)[:20]],
                    "extra": [list(value) for value in sorted(extra)[:20]],
                    "missing_count": len(missing),
                    "extra_count": len(extra),
                }
        if any_mismatch and len(mismatch_paragraphs) < 20:
            mismatch_paragraphs.append(paragraph_mismatch)

    parity_equal = not any(mismatch_counts.values())
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "sentence_limit": limit_sentences,
        "sentence_count": len(sentences),
        "token_count": token_count,
        "paragraph_count": len(expected),
        "sentences_with_emitted_a2_delta": admitted_sentence_count,
        "scope": {
            "operator_families": list(FAMILY_NAMES),
            "factor_type_symbol_ids": list(factor_type_ids),
            "objects_require_sentence_boundary_promotion": True,
            "selected_paragraphs_complete": True,
            "selected_paragraph_sentence_child_count": coverage["sentence_child_count"],
            "later_parent_reconciliation_in_scope": False,
            "actor_profiles_in_scope": False,
            "resolved_demands_in_scope": False,
            "global_lookup_in_scope": False,
        },
        "parity": {
            "equal": parity_equal,
            "mismatch_paragraph_count_by_family": mismatch_counts,
            "missing_key_count_by_family": missing_counts,
            "extra_key_count_by_family": extra_counts,
            "first_mismatches": mismatch_paragraphs,
        },
        "work": {
            "transported_sentence_delta_count": len(sentences),
            "paragraph_fusion_step_count": fusion_steps,
            "source_interior_rescan_count": source_interior_rescans,
            "zero_source_interior_rescan": source_interior_rescans == 0,
            "certification_reexecutes_a2_from_sentence_authority": True,
        },
        "timing_ns": {
            "load_sentence_lexicon_profile_membership": load_ns,
            "a2_sparse_family_solve": a2_ns,
            "sentence_to_paragraph_transport": transport_ns,
            "paragraph_fusion": fusion_ns,
            "scoped_boundary_authority_read": authority_ns,
        },
        "authority": {
            "comparison_surface": "transported paragraph boundary authority",
            "whole_paragraph_frontier_equality_claimed": False,
            "database_mutations_performed": False,
            "provider_io_performed": False,
            "independent_semantic_authority_created": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref")
    parser.add_argument("--limit-sentences", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = benchmark_b1_1_a2_paragraph_authority_parity(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
        limit_sentences=args.limit_sentences,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    green = bool(
        receipt["parity"]["equal"]
        and receipt["work"]["zero_source_interior_rescan"]
    )
    return 0 if green else 2


if __name__ == "__main__":
    raise SystemExit(main())
