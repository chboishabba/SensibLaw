#!/usr/bin/env python3
"""Read-only parity/work benchmark for sparse packed normative admission.

This benchmark measures the N-wide cheap admission pass separately from the
E-wide admitted topology/factor solve. It compares the sparse local delta with
the already-parity-tested eager packed delta, then compares durable materialized
output with the current reference normative projection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark_fibre_local_numeric_layout import _load_sentences
from scripts.benchmark_packed_normative_parity import (
    _load_operator_lexicon,
    _reference_normative_projection,
    _reference_tokens,
)
from src.pnf.fibre_local_numeric import pack_sentence_fibre
from src.pnf.fibre_local_relational_bridge import localize_relational_sentence
from src.pnf.numeric_operator_composition import compose_numeric_sentence
from src.pnf.packed_normative_admission import (
    build_normative_admission_plan,
    compose_sparse_packed_normative_delta,
)
from src.pnf.packed_numeric_composition import (
    compose_packed_normative_delta,
    materialize_normative_delta,
)

CONTRACT = "sensiblaw.sparse-packed-normative-parity.v0_2"


def benchmark_sparse_packed_normative_parity(
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
    plan = build_normative_admission_plan(lexicon)
    load_ns = monotonic_ns() - load_started

    sparse_solve_ns = 0
    eager_solve_ns = 0
    materialize_ns = 0
    reference_ns = 0
    local_delta_mismatch_count = 0
    authority_mismatch_count = 0
    admitted_fibre_count = 0
    topology_build_count = 0
    factor_build_count = 0
    normative_sentence_count = 0
    normative_factor_count = 0
    first_local_mismatches: list[int] = []
    first_authority_mismatches: list[int] = []
    normative_factor_type_id = int(
        lexicon.factor_type_ids["semantic.normative_relation"]
    )

    for sentence_index, sentence in enumerate(sentences):
        local = localize_relational_sentence(sentence)
        packed = pack_sentence_fibre(local)
        ordered_rows = tuple(
            sorted(sentence.tokens, key=lambda item: item.local_token_ordinal)
        )
        token_ids = tuple(row.token_id for row in ordered_rows)
        reference_tokens = _reference_tokens(sentence)
        synthetic_region_id = sentence_index + 1

        started = monotonic_ns()
        sparse = compose_sparse_packed_normative_delta(
            packed,
            lexicon,
            plan=plan,
        )
        sparse_solve_ns += monotonic_ns() - started
        admitted_fibre_count += sparse.work.admitted_fibres
        topology_build_count += sparse.work.topology_builds
        factor_build_count += sparse.work.factor_builds

        started = monotonic_ns()
        eager_delta = compose_packed_normative_delta(packed, lexicon)
        eager_solve_ns += monotonic_ns() - started
        if sparse.delta != eager_delta:
            local_delta_mismatch_count += 1
            if len(first_local_mismatches) < 20:
                first_local_mismatches.append(sentence_index)

        started = monotonic_ns()
        materialized = materialize_normative_delta(
            sparse.delta,
            region_id=synthetic_region_id,
            token_ids_by_ordinal=token_ids,
        )
        materialize_ns += monotonic_ns() - started

        started = monotonic_ns()
        reference = compose_numeric_sentence(
            region_id=synthetic_region_id,
            tokens=reference_tokens,
            lexicon=lexicon,
        )
        reference_ns += monotonic_ns() - started
        projected = _reference_normative_projection(
            reference,
            normative_factor_type_id,
        )

        normative_factor_count += len(materialized.factors)
        if materialized.factors:
            normative_sentence_count += 1
        if materialized != projected:
            authority_mismatch_count += 1
            if len(first_authority_mismatches) < 20:
                first_authority_mismatches.append(sentence_index)

    sentence_count = len(sentences)
    token_count = sum(len(sentence.tokens) for sentence in sentences)
    local_delta_equal = local_delta_mismatch_count == 0
    authority_equal = authority_mismatch_count == 0
    sparse_improvement = (
        (eager_solve_ns - sparse_solve_ns) / eager_solve_ns
        if eager_solve_ns > 0
        else None
    )
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "sentence_limit": limit_sentences,
        "sentence_count": sentence_count,
        "token_count": token_count,
        "normative_sentence_count": normative_sentence_count,
        "normative_factor_count": normative_factor_count,
        "local_delta_equal": local_delta_equal,
        "local_delta_mismatch_count": local_delta_mismatch_count,
        "first_local_delta_mismatch_sentence_indices": first_local_mismatches,
        "authority_equal": authority_equal,
        "mismatch_count": authority_mismatch_count,
        "first_mismatch_sentence_indices": first_authority_mismatches,
        "work": {
            "admission_check_count": sentence_count,
            "admitted_fibre_count": admitted_fibre_count,
            "topology_build_count": topology_build_count,
            "factor_build_count": factor_build_count,
            "topology_builds_equal_admitted_fibres": (
                topology_build_count == admitted_fibre_count
            ),
            "admission_fraction": (
                admitted_fibre_count / sentence_count if sentence_count else 0.0
            ),
        },
        "timing_ns": {
            "postgres_and_lexicon_read": load_ns,
            "sparse_packed_normative_solve": sparse_solve_ns,
            "eager_packed_normative_solve": eager_solve_ns,
            "sparse_wall_improvement_vs_eager": sparse_improvement,
            "authority_id_materialization": materialize_ns,
            "reference_full_sentence_composition": reference_ns,
        },
        "authority": {
            "database_mutations_performed": False,
            "provider_io_performed": False,
            "synthetic_region_ids_are_benchmark_only": True,
            "token_ids_applied_only_at_materialization": True,
            "comparison_scope": "normative/modal projection",
            "rejected_fibre_means_normative_projection_only": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref")
    parser.add_argument("--limit-sentences", type=int, default=10_000)
    parser.add_argument("--output")
    args = parser.parse_args()

    receipt = benchmark_sparse_packed_normative_parity(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
        limit_sentences=args.limit_sentences,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
    print(rendered)
    return 0 if receipt["authority_equal"] and receipt["local_delta_equal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
