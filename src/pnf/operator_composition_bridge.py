"""Apply generic operator composition to an existing document compilation.

The bridge reconstructs the public parser token record from the stored annotation
layer.  It never reparses text.  This makes the probe exercise the same parser
observations while the composition phase is being validated for direct inclusion
in the compiler pipeline.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.language.operator_composition import compose_operator_factors
from src.policy.carriers.canonical import canonical_sha256


OPERATOR_COMPOSITION_BRIDGE_CONTRACT = "pnf-operator-composition-bridge:v0_1"


def _parsed_document_from_layer(layer: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[int, dict[str, Any]] = {}
    for row in layer.get("token_annotations") or ():
        index = int(row.get("token_index", -1))
        if index < 0:
            continue
        annotation_type = str(row.get("annotation_type") or "")
        if not annotation_type.startswith("parser."):
            continue
        values.setdefault(index, {})[annotation_type.removeprefix("parser.")] = row.get("value")

    spans_by_ref: dict[str, Mapping[str, Any]] = {}
    token_ref_by_index: dict[int, str] = {}
    for row in layer.get("span_annotations") or ():
        if str(row.get("annotation_type") or "") != "parser_token":
            continue
        index = int(row.get("start_token", -1))
        if index < 0:
            continue
        span_ref = str(row.get("span_ref") or "")
        spans_by_ref[span_ref] = row
        token_ref_by_index[index] = span_ref
        payload = row.get("value") or {}
        values.setdefault(index, {}).update(
            {
                "start": int(payload.get("start_char", 0)),
                "end": int(payload.get("end_char", 0)),
            }
        )

    head_by_index: dict[int, int] = {}
    dependency_by_index: dict[int, str] = {}
    index_by_ref = {ref: index for index, ref in token_ref_by_index.items()}
    for row in layer.get("relation_annotations") or ():
        if str(row.get("relation_type") or "") != "parser.dependency_head":
            continue
        left_ref = str(row.get("left_ref") or "")
        token_index = index_by_ref.get(left_ref)
        if token_index is None:
            continue
        payload = row.get("payload") or {}
        head_by_index[token_index] = int(payload.get("head_index", token_index))
        dependency_by_index[token_index] = str(payload.get("dependency") or "")

    by_sentence: dict[int, list[dict[str, Any]]] = {}
    for index, payload in sorted(values.items()):
        sentence_index = int(payload.get("sentence", 0) or 0)
        token = {
            "index": index,
            "text": str(payload.get("surface") or ""),
            "lemma": str(payload.get("lemma") or payload.get("surface") or ""),
            "pos": str(payload.get("pos") or ""),
            "tag": str(payload.get("tag") or ""),
            "morph": payload.get("morphology") or {},
            "dep": dependency_by_index.get(index, str(payload.get("dependency") or "")),
            "head_index": head_by_index.get(index, index),
            "start": int(payload.get("start", 0)),
            "end": int(payload.get("end", 0)),
        }
        by_sentence.setdefault(sentence_index, []).append(token)

    return {
        "sents": [
            {"tokens": sorted(rows, key=lambda row: int(row["index"]))}
            for _sentence_index, rows in sorted(by_sentence.items())
        ],
        "parser_receipt": {"source": "stored_annotation_layer", "reparsed": False},
    }


def _projection_ready_factor(row: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(row))
    metadata = dict(value.get("metadata") or {})
    factor_type = str(value.get("factor_type") or "")
    value.update(
        {
            "factor_type_ref": factor_type,
            "factor_revision_ref": str(metadata.get("factor_revision_ref") or ""),
            "structural_signature_ref": str(metadata.get("structural_signature_ref") or ""),
            "predicate_ref": str(metadata.get("predicate_ref") or factor_type),
            "role_bindings": dict(metadata.get("role_bindings") or {}),
            "qualifier_state": dict(metadata.get("qualifier_state") or {}),
            "wrapper_state": dict(metadata.get("wrapper_state") or {}),
            "provenance_refs": list(metadata.get("provenance_refs") or ()),
            "residual_refs": list(value.get("residuals") or ()),
        }
    )
    return value


def apply_operator_composition_to_compilation(
    compilation: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compilation with operator factors added to both PNF graph views."""

    result = deepcopy(dict(compilation))
    artifacts = deepcopy(dict(result.get("artifacts") or {}))
    layer = artifacts.get("semantic_annotation_layer") or {}
    parsed_document = _parsed_document_from_layer(layer)
    document_ref = str(result.get("document_ref") or "")
    factors = compose_operator_factors(
        document_ref=document_ref,
        parsed_document=parsed_document,
    )
    factor_rows = tuple(_projection_ready_factor(row.to_dict()) for row in factors)

    for graph_name in ("pnf_graph", "refined_pnf_graph"):
        graph = deepcopy(dict(artifacts.get(graph_name) or {}))
        existing = {
            str(row.get("factor_ref") or ""): deepcopy(dict(row))
            for row in graph.get("factors") or ()
            if isinstance(row, Mapping)
        }
        for row in factor_rows:
            existing[str(row["factor_ref"])] = deepcopy(dict(row))
        graph["factors"] = [existing[key] for key in sorted(existing)]
        graph["graph_ref"] = "pnf-graph:" + canonical_sha256(
            {
                "prior_graph_ref": graph.get("graph_ref"),
                "contract": OPERATOR_COMPOSITION_BRIDGE_CONTRACT,
                "factor_refs": sorted(existing),
            }
        )
        artifacts[graph_name] = graph

    artifacts["operator_composition"] = {
        "contract_ref": OPERATOR_COMPOSITION_BRIDGE_CONTRACT,
        "parser_observation_source": "semantic_annotation_layer",
        "reparsed": False,
        "factor_refs": [row.factor_ref for row in factors],
        "factor_count": len(factors),
        "authority": "candidate_pnf_only",
    }
    result["artifacts"] = artifacts
    return result


__all__ = [
    "OPERATOR_COMPOSITION_BRIDGE_CONTRACT",
    "apply_operator_composition_to_compilation",
]
