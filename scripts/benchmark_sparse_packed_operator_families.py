#!/usr/bin/env python3
"""Read-only tranche receipt for fused packed operator-family admission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_fibre_local_numeric_layout import _load_sentences
from scripts.benchmark_packed_normative_parity import _load_operator_lexicon, _reference_tokens
from src.pnf.fibre_local_numeric import pack_sentence_fibre
from src.pnf.fibre_local_relational_bridge import localize_relational_sentence
from src.pnf.numeric_operator_composition import compose_numeric_sentence
from src.pnf.packed_numeric_composition import materialize_normative_delta
from src.pnf.packed_operator_family_admission import (
    CONDITION,
    EXCEPTION,
    FAMILY_NAMES,
    NORMATIVE,
    TRANSITION,
    build_operator_family_admission_plan,
    compose_sparse_packed_operator_families,
)

CONTRACT = "sensiblaw.sparse-packed-operator-families.v0_1"
FACTOR_TYPES = {
    NORMATIVE: "semantic.normative_relation",
    CONDITION: "semantic.legal_condition",
    EXCEPTION: "semantic.legal_exception",
    TRANSITION: "semantic.legal_transition",
}


def _family_projection(closure: Any, factor_type_id: int) -> tuple[tuple[Any, ...], ...]:
    factors = tuple(row for row in closure.factors if row.factor_type_symbol_id == factor_type_id)
    token_ids = {slot.source_token_id for row in factors for slot in row.slots}
    objects = tuple(row for row in closure.objects if row.source_token_id in token_ids)
    demands = tuple(row for row in closure.demands if row.expected_factor_type_symbol_id == factor_type_id)
    return objects, factors, demands


def benchmark(database_url: str, *, run_ref: str, limit_sentences: int) -> dict[str, Any]:
    sentences = _load_sentences(
        database_url,
        run_ref=run_ref,
        document_ref=None,
        limit_sentences=limit_sentences,
    )
    lexicon = _load_operator_lexicon(database_url)
    plan = build_operator_family_admission_plan(lexicon)
    admission_checks = 0
    topology_builds = 0
    admitted_fibres = 0
    family_exposure = {family: 0 for family in FAMILY_NAMES}
    family_solves = {family: 0 for family in FAMILY_NAMES}
    factor_counts = {family: 0 for family in FAMILY_NAMES}
    mismatch_count = 0
    first_mismatches: list[int] = []
    sparse_ns = 0
    reference_ns = 0

    for index, sentence in enumerate(sentences):
        local = localize_relational_sentence(sentence)
        packed = pack_sentence_fibre(local)
        token_ids = tuple(row.token_id for row in sorted(sentence.tokens, key=lambda row: row.local_token_ordinal))
        started = monotonic_ns()
        result = compose_sparse_packed_operator_families(packed, lexicon, plan=plan)
        sparse_ns += monotonic_ns() - started
        admission_checks += result.work.admission_checks
        topology_builds += result.work.topology_build_count
        admitted_fibres += result.work.admitted_fibre_count
        for family in FAMILY_NAMES:
            family_exposure[family] += int(result.admission.admitted(family))
            family_solves[family] += result.work.family_solve_counts[family]
            factor_counts[family] += result.work.factor_build_counts[family]

        started = monotonic_ns()
        reference = compose_numeric_sentence(
            region_id=index + 1,
            tokens=_reference_tokens(sentence),
            lexicon=lexicon,
        )
        reference_ns += monotonic_ns() - started
        actual = []
        for family in FAMILY_NAMES:
            materialized = materialize_normative_delta(
                result.deltas[family], region_id=index + 1, token_ids_by_ordinal=token_ids
            )
            actual.append((family, materialized))
            expected = _family_projection(reference, lexicon.factor_type_ids[FACTOR_TYPES[family]])
            if (materialized.objects, materialized.factors, materialized.demands) != expected:
                mismatch_count += 1
                if len(first_mismatches) < 20:
                    first_mismatches.append(index)

    sentence_count = len(sentences)
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "sentence_limit": limit_sentences,
        "sentence_count": sentence_count,
        "token_count": sum(len(sentence.tokens) for sentence in sentences),
        "local_delta_mismatch_count": mismatch_count,
        "first_mismatch_sentence_indices": first_mismatches,
        "authority_parity": mismatch_count == 0,
        "work": {
            "packed_scan_count": admission_checks,
            "admitted_fibre_count": admitted_fibres,
            "topology_build_count": topology_builds,
            "topology_builds_equal_admitted_fibres": topology_builds == admitted_fibres,
            "family_exposure_counts": family_exposure,
            "family_solve_counts": family_solves,
            "factor_build_counts": factor_counts,
        },
        "timing_ns": {
            "sparse_packed_fused_solve": sparse_ns,
            "reference_full_composition": reference_ns,
            "sparse_wall_improvement_vs_reference": (
                (reference_ns - sparse_ns) / reference_ns if reference_ns else None
            ),
        },
        "receipt": {
            "database_mutations_performed": False,
            "provider_io_performed": False,
            "durable_ids_used_in_local_solve": False,
            "authority_ids_applied_only_during_materialization": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--limit-sentences", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = benchmark(args.database_url, run_ref=args.run_ref, limit_sentences=args.limit_sentences)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
