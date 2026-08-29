"""Gate-A entrypoint for the optimized direct semantic benchmark.

This deliberately does not change the public production default. It runs the
existing streaming executor in DIRECT mode, replaces the legacy compatibility
return surface with receipt/evidence authority, and refuses to return unless the
database proves that no parser sentence/token/entity projection was materialised.
The same receipt records the first Agda performance ratio against observed spaCy
partition time.
"""

from __future__ import annotations

from pathlib import Path
from time import monotonic_ns
from typing import Any, Callable, Mapping

from src.storage.postgres.direct_semantic_carrier import (
    DirectSentenceCarrier,
    direct_execution_summary,
)
from src.storage.postgres.semantic_execution_mode import SemanticExecutionMode
from src.storage.postgres.spacy_parser_model import ParserStreamingPolicy, connect
from src.storage.postgres.streaming_spacy_execution import run_streaming_spacy_execution


def _direct_zero_projection_receipt(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, int]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM execution.semantic_parser_sentence
                      WHERE run_ref = %s AND document_ref = %s),
                    (SELECT count(*) FROM execution.semantic_parser_token
                      WHERE run_ref = %s AND document_ref = %s),
                    (SELECT count(*) FROM execution.semantic_parser_entity_span
                      WHERE run_ref = %s AND document_ref = %s),
                    (SELECT count(*) FROM execution.semantic_pnf_source_evidence
                      WHERE run_ref = %s AND document_ref = %s),
                    COALESCE((
                        SELECT sum(elapsed_ns)
                          FROM execution.semantic_parser_partition_receipt
                         WHERE run_ref = %s AND document_ref = %s
                    ), 0)
                """,
                (
                    run_ref, document_ref,
                    run_ref, document_ref,
                    run_ref, document_ref,
                    run_ref, document_ref,
                    run_ref, document_ref,
                ),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("direct Gate-A projection receipt is missing")
    sentence_rows, token_rows, entity_rows, evidence_rows, spacy_ns = map(int, row)
    if sentence_rows or token_rows or entity_rows:
        raise RuntimeError(
            "direct Gate-A violated zero parser projection: "
            f"sentences={sentence_rows} tokens={token_rows} entities={entity_rows}"
        )
    return {
        "parser_sentence_writes": sentence_rows,
        "parser_token_writes": token_rows,
        "parser_entity_writes": entity_rows,
        "stable_evidence_rows": evidence_rows,
        "spacy_observed_ns": spacy_ns,
    }


def run_direct_benchmark_execution(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text: str,
    parser_contract_ref: str,
    artifact_root: str | Path,
    worker_count: int = 2,
    policy: ParserStreamingPolicy | None = None,
    progress_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> DirectSentenceCarrier:
    """Run the Agda-correct direct lane and return only if Gate A is satisfied."""

    started_ns = monotonic_ns()
    compatibility = run_streaming_spacy_execution(
        database_url=database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        canonical_text=canonical_text,
        parser_contract_ref=parser_contract_ref,
        artifact_root=artifact_root,
        worker_count=worker_count,
        policy=policy,
        progress_observer=progress_observer,
        semantic_execution_mode=SemanticExecutionMode.DIRECT,
    )
    total_ns = max(0, monotonic_ns() - started_ns)
    summary = direct_execution_summary(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=compatibility.summary.source_ref,
        parser_contract_ref=parser_contract_ref,
    )
    if summary.coverage_state != "complete":
        raise RuntimeError("direct Gate-A coverage did not close")
    zero_projection = _direct_zero_projection_receipt(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    spacy_ns = int(zero_projection["spacy_observed_ns"])
    ratio = (float(total_ns) / float(spacy_ns)) if spacy_ns > 0 else None
    receipt = dict(compatibility["parser_receipt"])
    receipt.update(zero_projection)
    receipt.update(
        {
            "sentence_count": summary.sentence_count,
            "token_count": summary.token_count,
            "entity_count": summary.entity_count,
            "semantic_execution_mode": SemanticExecutionMode.DIRECT.value,
            "authority": "stable_source_evidence_and_direct_pnf_hyperfabric",
            "gate_a_benchmark_ready": True,
            "optimized_direct_total_ns": total_ns,
            "direct_over_spacy_ratio": ratio,
            "agda_first_stage_target_ratio": 2.0,
            "agda_first_stage_target_met": ratio is not None and ratio <= 2.0,
        }
    )
    return DirectSentenceCarrier(
        database_url=database_url,
        canonical_text=canonical_text,
        summary=summary,
        parser_receipt=receipt,
    )


__all__ = ["run_direct_benchmark_execution"]
