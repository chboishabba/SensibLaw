from __future__ import annotations

from src.language.operator_composition import compose_operator_factors
from src.pnf.legal_adjunct import project_legal_ir


def _parsed() -> dict:
    return {
        "sents": [
            {
                "tokens": [
                    {"index": 0, "text": "person", "lemma": "person", "pos": "NOUN", "dep": "nsubj", "head_index": 3, "start": 0, "end": 6},
                    {"index": 1, "text": "must", "lemma": "must", "pos": "AUX", "dep": "aux", "head_index": 3, "start": 7, "end": 11},
                    {"index": 2, "text": "not", "lemma": "not", "pos": "PART", "dep": "neg", "head_index": 3, "start": 12, "end": 15},
                    {"index": 3, "text": "drive", "lemma": "drive", "pos": "VERB", "dep": "ROOT", "head_index": 3, "start": 16, "end": 21},
                    {"index": 4, "text": "vehicle", "lemma": "vehicle", "pos": "NOUN", "dep": "obj", "head_index": 3, "start": 22, "end": 29},
                    {"index": 5, "text": "unless", "lemma": "unless", "pos": "SCONJ", "dep": "mark", "head_index": 6, "start": 30, "end": 36},
                    {"index": 6, "text": "licensed", "lemma": "license", "pos": "VERB", "dep": "advcl", "head_index": 3, "start": 37, "end": 45},
                ]
            },
            {
                "tokens": [
                    {"index": 7, "text": "section", "lemma": "section", "pos": "NOUN", "dep": "nsubjpass", "head_index": 9, "start": 47, "end": 54},
                    {"index": 8, "text": "is", "lemma": "be", "pos": "AUX", "dep": "auxpass", "head_index": 9, "start": 55, "end": 57},
                    {"index": 9, "text": "repealed", "lemma": "repeal", "pos": "VERB", "dep": "ROOT", "head_index": 9, "start": 58, "end": 66},
                ]
            },
        ]
    }


def _projection_row(factor) -> dict:
    row = factor.to_dict()
    metadata = row["metadata"]
    return {
        **row,
        "factor_type_ref": row["factor_type"],
        "factor_revision_ref": metadata["factor_revision_ref"],
        "structural_signature_ref": metadata["structural_signature_ref"],
        "predicate_ref": metadata["predicate_ref"],
        "role_bindings": metadata["role_bindings"],
        "qualifier_state": metadata["qualifier_state"],
        "wrapper_state": metadata["wrapper_state"],
        "provenance_refs": metadata["provenance_refs"],
        "residual_refs": row["residuals"],
    }


def test_generic_parser_observations_compose_legal_relevant_pnf() -> None:
    factors = compose_operator_factors(document_ref="document:test", parsed_document=_parsed())
    factor_types = {row.factor_type for row in factors}

    assert "semantic.normative_relation" in factor_types
    assert "semantic.legal_exception" in factor_types
    assert "semantic.legal_transition" in factor_types

    normative = next(row for row in factors if row.factor_type == "semantic.normative_relation")
    assert normative.metadata["predicate_ref"] == "normative.prohibition"
    assert normative.metadata["qualifier_state"]["polarity"] == "negative"
    assert set(normative.metadata["role_bindings"]) >= {"bearer", "conduct", "object"}
    assert "legal_time_unresolved" in normative.residuals

    observations = project_legal_ir(_projection_row(row) for row in factors)
    assert len(observations) == len(factors)
    assert {row.predicate_ref for row in observations} >= {
        "normative.prohibition",
        "legal.exception_candidate",
        "legal.repeal",
    }
    assert all(row.projection_state == "candidate" for row in observations)
