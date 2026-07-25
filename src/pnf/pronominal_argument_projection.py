"""Parser-observation to generic pronominal argument factors.

This projection is corpus-neutral.  It consumes parser POS/morphology/dependency
observations and emits candidate-only ``semantic.argument_reference`` factors with
span, relation, and source-factor provenance.  It contains no pronoun vocabulary.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256

PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT = "postgres-semantic-compiler:v0_8"
PRONOMINAL_ARGUMENT_DECLARATION_REF = "grammar:pnf:parser-pronominal-argument:v0_3"


def _refs(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _observation_pos(row: Mapping[str, Any]) -> str:
    return str(
        row.get("pos")
        or row.get("upos")
        or row.get("parser_pos")
        or row.get("part_of_speech")
        or ""
    ).upper()


def _role_for_dependency(dependency: str) -> str:
    value = dependency.casefold()
    if value in {"nsubj", "csubj", "nsubj:pass", "expl"}:
        return "subject"
    if value in {"obj", "dobj", "iobj"}:
        return "object"
    if value.startswith("obl"):
        return "oblique"
    return "argument"


def _source_factor_ref(row: Mapping[str, Any]) -> str | None:
    for key in ("source_factor_ref", "head_factor_ref", "governor_factor_ref"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def _factor_from_observation(document_ref: str, row: Mapping[str, Any]) -> dict[str, Any]:
    observation_ref = str(
        row.get("observation_ref")
        or row.get("token_ref")
        or row.get("id")
        or ""
    ).strip()
    if not observation_ref:
        raise ValueError("parser pronominal observation requires a stable reference")
    span_ref = str(row.get("span_ref") or row.get("source_span_ref") or "").strip()
    dependency = str(
        row.get("dependency") or row.get("dep") or row.get("parser_dependency") or ""
    ).strip()
    relation_ref = str(row.get("relation_ref") or row.get("dependency_ref") or "").strip()
    morphology = row.get("morphology") or row.get("morph") or row.get("parser_morphology") or {}
    if not isinstance(morphology, Mapping):
        morphology = {"raw": str(morphology)}
    role = _role_for_dependency(dependency)
    source_factor_ref = _source_factor_ref(row)
    factor_identity = {
        "document_ref": document_ref,
        "observation_ref": observation_ref,
        "span_ref": span_ref,
        "dependency": dependency,
        "relation_ref": relation_ref,
        "role": role,
        "source_factor_ref": source_factor_ref,
        "declaration_ref": PRONOMINAL_ARGUMENT_DECLARATION_REF,
    }
    factor_ref = "factor:" + canonical_sha256(factor_identity)
    evidence_refs = _refs(
        (
            observation_ref,
            span_ref,
            relation_ref,
            source_factor_ref,
            PRONOMINAL_ARGUMENT_DECLARATION_REF,
        )
    )
    return {
        "factor_ref": factor_ref,
        "factor_type": "semantic.argument_reference",
        "alternatives": [
            {
                "alternative_ref": f"{factor_ref}:parser-pronominal-argument",
                "value": {
                    "observation_ref": observation_ref,
                    "role": role,
                    "dependency": dependency,
                    "relation_ref": relation_ref or None,
                    "source_factor_ref": source_factor_ref,
                },
                "type_ref": "semantic.pronominal_argument_candidate",
                "derivation_refs": [PRONOMINAL_ARGUMENT_DECLARATION_REF],
                "evidence_refs": list(evidence_refs),
                "authority_state": "candidate_only",
            }
        ],
        "constraints": [],
        "residuals": ["antecedent_unresolved", "referential_type_unresolved"],
        "closure_state": "requires_external_resolution",
        "metadata": {
            "parser_pos": "PRON",
            "parser_morphology": dict(morphology),
            "parser_dependency": dependency,
            "role": role,
            "relation_ref": relation_ref or None,
            "source_span_refs": [span_ref] if span_ref else [],
            "parser_observation_refs": [observation_ref],
            "source_factor_ref": source_factor_ref,
            "provenance_refs": list(evidence_refs),
            "projection_contract": PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT,
            "semantic_state_promoted": False,
        },
    }


def project_parser_pronominal_arguments(
    *,
    document_ref: str,
    parser_observations: Sequence[Mapping[str, Any]],
    existing_factors: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    by_ref = {
        str(row.get("factor_ref") or ""): dict(row)
        for row in existing_factors
        if str(row.get("factor_ref") or "")
    }
    for row in parser_observations:
        if _observation_pos(row) != "PRON":
            continue
        factor = _factor_from_observation(document_ref, row)
        by_ref.setdefault(str(factor["factor_ref"]), factor)
    return tuple(by_ref[key] for key in sorted(by_ref))


def attach_parser_pronominal_arguments(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    if artifacts.get("pronominal_argument_projection_contract") == (
        PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT
    ):
        return dict(artifacts)
    result = dict(artifacts)
    graph = dict(artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {})
    observations = tuple(
        row
        for row in (
            artifacts.get("parser_observations")
            or (artifacts.get("parser_bundle") or {}).get("observations")
            or ()
        )
        if isinstance(row, Mapping)
    )
    factors = project_parser_pronominal_arguments(
        document_ref=str(graph.get("document_ref") or artifacts.get("document_ref") or ""),
        parser_observations=observations,
        existing_factors=tuple(
            row for row in graph.get("factors") or () if isinstance(row, Mapping)
        ),
    )
    graph["factors"] = list(factors)
    graph["graph_ref"] = "pnf-graph:" + canonical_sha256(
        {
            "document_ref": graph.get("document_ref"),
            "factors": graph["factors"],
            "constraints": graph.get("constraints") or (),
            "projection_contract": PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT,
        }
    )
    result["pnf_graph"] = graph
    result["refined_pnf_graph"] = graph
    result["pronominal_argument_projection_contract"] = (
        PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT
    )
    result["pronominal_argument_factor_refs"] = [
        row["factor_ref"]
        for row in factors
        if str(row.get("factor_type") or "") == "semantic.argument_reference"
        and str((row.get("metadata") or {}).get("parser_pos") or "") == "PRON"
    ]
    result["semantic_compiler_contract"] = PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT
    result["cache_compatible_with_pre_reference_artifacts"] = False
    return result


__all__ = [
    "PRONOMINAL_ARGUMENT_DECLARATION_REF",
    "PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT",
    "attach_parser_pronominal_arguments",
    "project_parser_pronominal_arguments",
]
