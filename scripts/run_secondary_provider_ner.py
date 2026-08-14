#!/usr/bin/env python3
"""Run a local secondary NER pass over only H9-relevant parser sentences.

No provider or model-download I/O is performed. The requested spaCy package must
already be installed. Results are appended as independently-provenanced entity
boundary observations and then projected through the existing provider-quality
gate.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from src.nlp.provider_ner import DEFAULT_PROVIDER_NER_MODEL, load_provider_ner
from src.storage.postgres.spacy_parser_model import connect


def _load_sentence_texts(cursor, *, consumer_ref: str, query_ref: str, policy_ref: str):
    cursor.execute(
        """
        WITH scoped AS MATERIALIZED (
            SELECT DISTINCT admission.demand_id
              FROM execution.semantic_pnf_h9_external_admission_v1 admission
             WHERE admission.consumer_ref=%s
               AND admission.query_ref=%s
               AND admission.policy_ref=%s
               AND admission.contract_id IS NOT NULL
        ), sentence_ids AS MATERIALIZED (
            SELECT DISTINCT token.sentence_ref
              FROM scoped
              JOIN execution.semantic_pnf_demand_strong_occurrence_support_v1 strong
                USING(demand_id)
              JOIN execution.semantic_pnf_object_token_support object_token
                ON object_token.object_id=strong.object_id
              JOIN execution.semantic_parser_token token
                ON token.token_id=object_token.token_id
               AND token.representation_version=2
        )
        SELECT sentence.run_ref,sentence.document_ref,sentence.sentence_ref,
               sentence.start_char,sentence.end_char,source.locator
          FROM sentence_ids
          JOIN execution.semantic_parser_sentence sentence USING(sentence_ref)
          JOIN execution.semantic_parser_partition partition
            ON partition.partition_ref=sentence.partition_ref
          JOIN execution.semantic_parser_source source
            ON source.source_ref=partition.source_ref
         ORDER BY sentence.run_ref,sentence.document_ref,sentence.start_char
        """,
        (consumer_ref, query_ref, policy_ref),
    )
    rows = cursor.fetchall()
    source_cache: dict[str, str] = {}
    result = []
    for run_ref, document_ref, sentence_ref, start_char, end_char, locator in rows:
        path = str(locator)
        text = source_cache.get(path)
        if text is None:
            text = Path(path).read_text(encoding="utf-8")
            source_cache[path] = text
        start = int(start_char)
        end = int(end_char)
        result.append(
            (
                text[start:end],
                {
                    "run_ref": str(run_ref),
                    "document_ref": str(document_ref),
                    "sentence_ref": str(sentence_ref),
                    "sentence_start": start,
                    "sentence_end": end,
                },
            )
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--consumer-ref", required=True)
    parser.add_argument("--query-ref", required=True)
    parser.add_argument("--policy-ref", default="")
    parser.add_argument(
        "--model",
        default=os.environ.get("SENSIBLAW_PROVIDER_NER_MODEL", DEFAULT_PROVIDER_NER_MODEL),
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--sentence-limit", type=int, default=0)
    args = parser.parse_args()

    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            sentence_inputs = _load_sentence_texts(
                cursor,
                consumer_ref=args.consumer_ref,
                query_ref=args.query_ref,
                policy_ref=args.policy_ref,
            )
    finally:
        connection.close()

    if args.sentence_limit > 0:
        sentence_inputs = sentence_inputs[: args.sentence_limit]

    nlp = load_provider_ner(args.model)
    model_version = str(nlp.meta.get("version") or "unknown")
    observations: list[dict[str, object]] = []
    for doc, metadata in nlp.pipe(
        sentence_inputs,
        as_tuples=True,
        batch_size=max(1, args.batch_size),
        n_process=1,
    ):
        sentence_start = int(metadata["sentence_start"])
        for entity in doc.ents:
            observations.append(
                {
                    **metadata,
                    "start_char": sentence_start + int(entity.start_char),
                    "end_char": sentence_start + int(entity.end_char),
                    "entity_type": str(entity.label_),
                    "surface": str(entity.text),
                }
            )

    pass_ref = f"provider-ner-pass:{uuid4().hex}"
    connection = connect(args.database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                # The new pass becomes current only if this transaction commits.
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_secondary_entity_pass
                       SET active=FALSE
                     WHERE model_name=%s
                       AND consumer_ref=%s
                       AND query_ref=%s
                       AND policy_ref=%s
                       AND active
                    """,
                    (args.model, args.consumer_ref, args.query_ref, args.policy_ref),
                )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_secondary_entity_pass
                        (pass_ref,model_name,model_version,consumer_ref,query_ref,
                         policy_ref,sentence_count,entity_count,active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                    RETURNING pass_id
                    """,
                    (
                        pass_ref,
                        args.model,
                        model_version,
                        args.consumer_ref,
                        args.query_ref,
                        args.policy_ref,
                        len(sentence_inputs),
                        len(observations),
                    ),
                )
                pass_id = int(cursor.fetchone()[0])

                symbol_cache: dict[tuple[int, str], int] = {}

                def symbol_id(kind_id: int, value: str) -> int:
                    key = (kind_id, value)
                    cached = symbol_cache.get(key)
                    if cached is not None:
                        return cached
                    cursor.execute(
                        "SELECT execution.ensure_semantic_symbol(%s::SMALLINT,%s)",
                        (kind_id, value),
                    )
                    resolved = int(cursor.fetchone()[0])
                    symbol_cache[key] = resolved
                    return resolved

                for observation in observations:
                    entity_type_symbol_id = symbol_id(8, str(observation["entity_type"]))
                    label_symbol_id = symbol_id(1, str(observation["surface"]))
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_secondary_entity_span
                            (pass_id,run_ref,document_ref,sentence_ref,start_char,end_char,
                             entity_type_symbol_id,label_symbol_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            pass_id,
                            observation["run_ref"],
                            observation["document_ref"],
                            observation["sentence_ref"],
                            observation["start_char"],
                            observation["end_char"],
                            entity_type_symbol_id,
                            label_symbol_id,
                        ),
                    )

                cursor.execute(
                    "SELECT execution.refresh_semantic_parser_provider_entity_candidates()"
                )
                candidate_refresh_rows = int(cursor.fetchone()[0])

                cursor.execute(
                    """
                    SELECT quality_state,count(*)::BIGINT
                      FROM execution.semantic_parser_secondary_entity_span_quality_v1
                     WHERE pass_id=%s
                     GROUP BY quality_state
                     ORDER BY quality_state
                    """,
                    (pass_id,),
                )
                quality_counts = {
                    str(int(state)): int(count) for state, count in cursor.fetchall()
                }
                cursor.execute(
                    """
                    SELECT count(DISTINCT candidate.provider_entity_candidate_id)::BIGINT
                      FROM execution.semantic_parser_provider_entity_candidate_current_v1 candidate
                      JOIN execution.semantic_parser_provider_entity_candidate_support support
                        ON support.provider_entity_candidate_id=candidate.provider_entity_candidate_id
                       AND support.active AND support.support_kind=2
                      JOIN execution.semantic_parser_secondary_entity_span span
                        ON span.secondary_entity_id=support.secondary_entity_id
                     WHERE span.pass_id=%s
                    """,
                    (pass_id,),
                )
                surviving_candidates = int(cursor.fetchone()[0])
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "pass_ref": pass_ref,
                "model_name": args.model,
                "model_version": model_version,
                "sentences_processed": len(sentence_inputs),
                "raw_secondary_entities": len(observations),
                "quality_counts": quality_counts,
                "surviving_provider_candidates": surviving_candidates,
                "candidate_refresh_rows": candidate_refresh_rows,
                "model_download_performed": False,
                "provider_io_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
