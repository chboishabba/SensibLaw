from __future__ import annotations

from src.pnf.streaming_operator_executor import (
    build_streaming_operator_state,
    parser_sentence_deltas,
)


def _parsed_document() -> dict[str, object]:
    return {
        "sents": [
            {
                "tokens": [
                    {
                        "index": 0,
                        "text": "Driver",
                        "lemma": "driver",
                        "pos": "NOUN",
                        "dep": "nsubj",
                        "head_index": 3,
                        "start": 0,
                        "end": 6,
                    },
                    {
                        "index": 1,
                        "text": "must",
                        "lemma": "must",
                        "pos": "AUX",
                        "dep": "aux",
                        "head_index": 3,
                        "start": 7,
                        "end": 11,
                    },
                    {
                        "index": 2,
                        "text": "not",
                        "lemma": "not",
                        "pos": "PART",
                        "dep": "neg",
                        "head_index": 3,
                        "start": 12,
                        "end": 15,
                    },
                    {
                        "index": 3,
                        "text": "drive",
                        "lemma": "drive",
                        "pos": "VERB",
                        "dep": "ROOT",
                        "head_index": 3,
                        "start": 16,
                        "end": 21,
                    },
                ]
            },
            {
                "tokens": [
                    {
                        "index": 4,
                        "text": "Owner",
                        "lemma": "owner",
                        "pos": "NOUN",
                        "dep": "nsubj",
                        "head_index": 6,
                        "start": 23,
                        "end": 28,
                    },
                    {
                        "index": 5,
                        "text": "may",
                        "lemma": "may",
                        "pos": "AUX",
                        "dep": "aux",
                        "head_index": 6,
                        "start": 29,
                        "end": 32,
                    },
                    {
                        "index": 6,
                        "text": "apply",
                        "lemma": "apply",
                        "pos": "VERB",
                        "dep": "ROOT",
                        "head_index": 6,
                        "start": 33,
                        "end": 38,
                    },
                ]
            },
        ],
        "parser_receipt": {
            "contract_ref": "parser:test:v1",
            "backend": "spacy",
        },
    }


def test_parser_projection_emits_complete_ordered_sentence_deltas() -> None:
    deltas = parser_sentence_deltas(
        document_ref="document:test",
        parsed_document=_parsed_document(),
    )

    assert [row.sequence_no for row in deltas] == [0, 1]
    assert [row.token_count for row in deltas] == [4, 3]
    assert all(row.coverage_complete for row in deltas)
    assert all(row.coverage_barrier == "sentence" for row in deltas)


def test_sentence_jobs_reduce_to_convergent_document_state() -> None:
    owner = build_streaming_operator_state(
        document_ref="document:test",
        parsed_document=_parsed_document(),
        closure_workers=2,
        partition_count=2,
    )
    payload = owner.to_dict()

    assert len(owner.ledger.receipts) == 2
    assert len(owner.ledger.proposals) == 2
    assert owner.fixed_point_certificate().local_fixed_point_reached is True
    predicates = {
        str(row.candidate_payload.get("predicate_ref"))
        for row in owner.ledger.proposals
    }
    assert "normative.prohibition" in predicates
    assert "normative.permission_candidate" in predicates
    assert payload["shared_graph_mutation"] is False
