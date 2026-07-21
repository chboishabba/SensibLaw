from __future__ import annotations

from src.pnf.operator_closure_benchmark import (
    NORMALIZED_OPERATOR_RULE_SET_REVISION,
    NormalizedOperatorZelphCodec,
    native_operator_proposals,
    normalized_operator_candidates,
)
from src.pnf.streaming_fixed_point import OwnerKey, SolverJob


def _job() -> SolverJob:
    tokens = (
        {
            "index": 0,
            "text": "must",
            "lemma": "must",
            "pos": "AUX",
            "dep": "aux",
            "head_index": 2,
        },
        {
            "index": 1,
            "text": "not",
            "lemma": "not",
            "pos": "PART",
            "dep": "neg",
            "head_index": 2,
        },
        {
            "index": 2,
            "text": "drive",
            "lemma": "drive",
            "pos": "VERB",
            "dep": "ROOT",
            "head_index": 2,
        },
        {
            "index": 3,
            "text": "unless",
            "lemma": "unless",
            "pos": "SCONJ",
            "dep": "mark",
            "head_index": 4,
        },
        {
            "index": 4,
            "text": "licensed",
            "lemma": "license",
            "pos": "VERB",
            "dep": "advcl",
            "head_index": 2,
        },
    )
    observations = tuple(
        {
            "observation_ref": f"observation:{index}",
            "observation_type": "parser.token",
            "token": token,
        }
        for index, token in enumerate(tokens)
    )
    return SolverJob(
        owner_key=OwnerKey(
            "document:1",
            "sentence:1",
            "semantic.operator_composition",
        ),
        declaration_ref="declaration:normalized-operator:v0_1",
        input_revision=1,
        input_refs=tuple(row["observation_ref"] for row in observations),
        input_payload={"observation_delta": {"observations": observations}},
        rule_set_revision=NORMALIZED_OPERATOR_RULE_SET_REVISION,
        coverage_requirements=("sentence",),
    )


def test_normalized_operator_lane_covers_prohibition_and_exception() -> None:
    job = _job()
    proposals = native_operator_proposals(job)
    predicates = {
        str(row.candidate_payload["predicate_ref"]) for row in proposals
    }

    assert "normative.prohibition" in predicates
    assert "legal.exception_candidate" in predicates


def test_zelph_codec_decodes_selected_candidates_to_native_proposals() -> None:
    job = _job()
    candidates = normalized_operator_candidates(job)
    triples = [
        {
            "subject": row.node,
            "predicate": "selected candidate",
            "object": "true",
        }
        for row in candidates
    ]
    decoded = NormalizedOperatorZelphCodec().decode_proposals(job, triples)

    assert tuple(row.proposal_ref for row in decoded) == tuple(
        row.proposal_ref for row in candidates
    )
