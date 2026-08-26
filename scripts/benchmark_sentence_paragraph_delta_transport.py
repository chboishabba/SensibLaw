#!/usr/bin/env python3
"""Read-only B1 corpus receipt for sentence->paragraph delta transport.

The benchmark uses the existing strict-v2 PostgreSQL sentence authority and the
already-authored sentence->paragraph region relation.  It runs the fused A2
operator-family solver once per sentence, projects only the emitted semantic
delta, transports that delta into paragraph-local coordinates, and fuses child
deltas without reopening sentence token state.

This tranche deliberately does *not* compare the result with the whole current
paragraph frontier: that frontier may contain later reconciliation, actor-profile,
scope, and promotion products.  Instead it validates B1's transport algebra
against an independent direct canonical union of the transported child deltas.
No database mutation or provider I/O is performed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any, Iterable

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.benchmark_fibre_local_numeric_layout import _load_sentences
from scripts.benchmark_packed_normative_parity import _load_operator_lexicon
from src.pnf.fibre_local_numeric import pack_sentence_fibre
from src.pnf.fibre_local_relational_bridge import localize_relational_sentence
from src.pnf.packed_operator_family_admission import (
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
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.sentence-paragraph-delta-transport.v0_1"
PARAGRAPH_REGION_KIND = 3


def _load_paragraph_membership(
    database_url: str,
    *,
    run_ref: str,
    sentence_refs: Iterable[str],
) -> dict[str, tuple[int, int]]:
    """Return sentence_ref -> (paragraph_region_id, child_ordinal).

    The relation is read from the existing authored PNF hierarchy.  B1 does not
    infer paragraphs from text or spans.  Missing/non-paragraph parents fail
    closed in the caller.
    """

    refs = tuple(dict.fromkeys(str(value) for value in sentence_refs))
    if not refs:
        return {}
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    WITH membership AS (
                        SELECT sentence.sentence_ref,
                               parent.region_id AS paragraph_region_id,
                               row_number() OVER (
                                   PARTITION BY parent.region_id
                                   ORDER BY child.start_char,
                                            child.end_char,
                                            child.region_id
                               ) - 1 AS child_ordinal
                          FROM execution.semantic_parser_sentence AS sentence
                          JOIN execution.semantic_pnf_sentence_region AS mapping
                            ON mapping.sentence_id = sentence.sentence_id
                          JOIN execution.semantic_pnf_region AS child
                            ON child.region_id = mapping.region_id
                          JOIN execution.semantic_pnf_region AS parent
                            ON parent.region_id = child.parent_region_id
                           AND parent.region_kind = %s
                         WHERE sentence.run_ref = %s
                           AND sentence.sentence_ref = ANY(%s)
                    )
                    SELECT sentence_ref, paragraph_region_id, child_ordinal
                      FROM membership
                     ORDER BY paragraph_region_id, child_ordinal, sentence_ref
                    """,
                    (PARAGRAPH_REGION_KIND, run_ref, list(refs)),
                )
                rows = tuple(cursor.fetchall())
    finally:
        connection.close()
    return {
        str(sentence_ref): (int(paragraph_id), int(child_ordinal))
        for sentence_ref, paragraph_id, child_ordinal in rows
    }


def _direct_union(
    deltas: Iterable[ParagraphSemanticDelta],
) -> ParagraphSemanticDelta:
    """Independent canonical-union reference for the B1 fusion law."""

    sentence_ordinals: set[int] = set()
    objects = set()
    factors = set()
    residuals = set()
    for delta in deltas:
        sentence_ordinals.update(delta.source_sentence_ordinals)
        objects.update(delta.objects)
        factors.update(delta.factors)
        residuals.update(delta.residuals)
    return ParagraphSemanticDelta(
        source_sentence_ordinals=tuple(sorted(sentence_ordinals)),
        objects=tuple(sorted(objects)),
        factors=tuple(sorted(factors)),
        residuals=tuple(sorted(residuals)),
    )


def benchmark_sentence_paragraph_delta_transport(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str | None = None,
    limit_sentences: int = 10_000,
) -> dict[str, Any]:
    if limit_sentences <= 0:
        raise ValueError("limit_sentences must be positive")

    load_started = monotonic_ns()
    sentences = _load_sentences(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        limit_sentences=limit_sentences,
    )
    lexicon = _load_operator_lexicon(database_url)
    plan = build_operator_family_admission_plan(lexicon)
    membership = _load_paragraph_membership(
        database_url,
        run_ref=run_ref,
        sentence_refs=(sentence.sentence_ref for sentence in sentences),
    )
    load_ns = monotonic_ns() - load_started

    missing_membership = [
        sentence.sentence_ref
        for sentence in sentences
        if sentence.sentence_ref not in membership
    ]
    if missing_membership:
        preview = missing_membership[:20]
        raise RuntimeError(
            "selected strict-v2 sentences are missing authored paragraph parents: "
            f"count={len(missing_membership)} first={preview!r}"
        )

    paragraph_children: dict[int, list[ParagraphSemanticDelta]] = defaultdict(list)
    a2_ns = 0
    sentence_delta_ns = 0
    transport_ns = 0
    source_token_rescans = 0
    admitted_sentence_count = 0
    transported_object_count = 0
    transported_factor_count = 0
    transported_residual_count = 0
    token_count = 0

    for sentence in sentences:
        local = localize_relational_sentence(sentence)
        packed = pack_sentence_fibre(local)
        token_count += packed.token_count

        started = monotonic_ns()
        a2 = compose_sparse_packed_operator_families(packed, lexicon, plan=plan)
        a2_ns += monotonic_ns() - started

        started = monotonic_ns()
        sentence_delta = sentence_semantic_delta_from_operator_families(
            sentence.sentence_ordinal,
            a2,
        )
        sentence_delta_ns += monotonic_ns() - started
        if sentence_delta.factors or sentence_delta.objects or sentence_delta.residuals:
            admitted_sentence_count += 1

        paragraph_id, child_ordinal = membership[sentence.sentence_ref]
        started = monotonic_ns()
        transported = transport_sentence_delta_to_paragraph(
            sentence_delta,
            child_ordinal=child_ordinal,
        )
        transport_ns += monotonic_ns() - started
        source_token_rescans += transported.work.source_token_rescan_count
        transported_object_count += transported.work.transported_object_count
        transported_factor_count += transported.work.transported_factor_count
        transported_residual_count += transported.work.transported_residual_count
        paragraph_children[paragraph_id].append(transported.delta)

    fusion_started = monotonic_ns()
    fused_by_paragraph: dict[int, ParagraphSemanticDelta] = {}
    fusion_object_inputs = 0
    fusion_factor_inputs = 0
    fusion_residual_inputs = 0
    fusion_steps = 0
    for paragraph_id, children in paragraph_children.items():
        current = ParagraphSemanticDelta((), (), (), ())
        for child in children:
            fused = fuse_paragraph_deltas(current, child)
            source_token_rescans += fused.work.source_token_rescan_count
            fusion_object_inputs += fused.work.object_inputs
            fusion_factor_inputs += fused.work.factor_inputs
            fusion_residual_inputs += fused.work.residual_inputs
            fusion_steps += 1
            current = fused.delta
        fused_by_paragraph[paragraph_id] = current
    fusion_ns = monotonic_ns() - fusion_started

    reference_started = monotonic_ns()
    mismatch_paragraph_ids: list[int] = []
    interface_key_mismatch_paragraph_ids: list[int] = []
    for paragraph_id, children in paragraph_children.items():
        direct = _direct_union(children)
        fused = fused_by_paragraph[paragraph_id]
        if fused != direct:
            if len(mismatch_paragraph_ids) < 20:
                mismatch_paragraph_ids.append(paragraph_id)
        if paragraph_interface_keys(fused) != paragraph_interface_keys(direct):
            if len(interface_key_mismatch_paragraph_ids) < 20:
                interface_key_mismatch_paragraph_ids.append(paragraph_id)
    reference_ns = monotonic_ns() - reference_started

    paragraph_count = len(paragraph_children)
    sentence_count = len(sentences)
    emitted_member_count = (
        transported_object_count
        + transported_factor_count
        + transported_residual_count
    )
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "sentence_limit": limit_sentences,
        "sentence_count": sentence_count,
        "token_count": token_count,
        "paragraph_count": paragraph_count,
        "sentences_with_emitted_delta": admitted_sentence_count,
        "transport_fusion_equal_direct_union": not mismatch_paragraph_ids,
        "transport_fusion_mismatch_count": len(mismatch_paragraph_ids),
        "first_transport_fusion_mismatch_paragraph_ids": mismatch_paragraph_ids,
        "interface_projection_equal_direct_union": not interface_key_mismatch_paragraph_ids,
        "interface_projection_mismatch_count": len(interface_key_mismatch_paragraph_ids),
        "first_interface_projection_mismatch_paragraph_ids": (
            interface_key_mismatch_paragraph_ids
        ),
        "work": {
            "sentence_delta_count": sentence_count,
            "paragraph_count": paragraph_count,
            "transported_object_count": transported_object_count,
            "transported_factor_count": transported_factor_count,
            "transported_residual_count": transported_residual_count,
            "transported_member_count": emitted_member_count,
            "fusion_step_count": fusion_steps,
            "fusion_object_inputs": fusion_object_inputs,
            "fusion_factor_inputs": fusion_factor_inputs,
            "fusion_residual_inputs": fusion_residual_inputs,
            "source_token_rescan_count": source_token_rescans,
            "zero_source_token_rescan": source_token_rescans == 0,
            "transported_members_per_source_token": (
                emitted_member_count / token_count if token_count else 0.0
            ),
        },
        "timing_ns": {
            "postgres_sentence_lexicon_membership_read": load_ns,
            "a2_sparse_family_solve": a2_ns,
            "sentence_delta_projection": sentence_delta_ns,
            "sentence_to_paragraph_transport": transport_ns,
            "paragraph_fusion": fusion_ns,
            "direct_union_reference_check": reference_ns,
            "b1_transport_plus_fusion": transport_ns + fusion_ns,
        },
        "authority": {
            "database_mutations_performed": False,
            "provider_io_performed": False,
            "paragraph_membership_source": "existing semantic_pnf sentence-region parent relation",
            "durable_token_ids_required_by_b1": False,
            "whole_paragraph_frontier_equality_claimed": False,
            "comparison_scope": "transport/fusion algebra over emitted A2 sentence deltas",
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

    receipt = benchmark_sentence_paragraph_delta_transport(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
        limit_sentences=args.limit_sentences,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    gates_green = bool(
        receipt["transport_fusion_equal_direct_union"]
        and receipt["interface_projection_equal_direct_union"]
        and receipt["work"]["zero_source_token_rescan"]
    )
    return 0 if gates_green else 2


if __name__ == "__main__":
    raise SystemExit(main())
